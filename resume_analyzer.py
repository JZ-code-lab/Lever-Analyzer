import os
import json
from datetime import datetime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from openai import OpenAI
from duckduckgo_search import DDGS

# API Key for OpenAI
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def is_rate_limit_error(exception: BaseException) -> bool:
    error_msg = str(exception)
    return "429" in error_msg or "rate limit" in error_msg.lower()

def get_company_research(company_name: str) -> str:
    """Uses FREE DuckDuckGo to research company industry."""
    if not company_name or len(company_name) < 2 or company_name.lower() in ["unknown", "none", "n/a"]:
        return ""
    
    try:
        # We use a small 'sleep' or limit workers to avoid being blocked
        with DDGS() as ddgs:
            query = f"{company_name} company industry niche"
            results = list(ddgs.text(query, max_results=1)) # Only 1 result for speed
            return results[0]['body'] if results else ""
    except Exception:
        return ""

def analyze_single_resume(resume_text: str, job_description: Optional[str], weighted_requirements: list[dict], jd_weight: float, technical_indicators: Optional[dict] = None, disqualifiers: Optional[list[str]] = None) -> dict:
    # --- 1. Extract every unique employer in the resume ---
    try:
        name_extract = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": (
                    "List EVERY unique employer mentioned in this resume, in reverse-chronological "
                    "order (most recent first). Return ONLY the company names, separated by commas, "
                    "no other text.\n\n"
                    f"{resume_text}"
                ),
            }],
            temperature=0,
        )
        companies = [c.strip() for c in (name_extract.choices[0].message.content or "").split(",") if c.strip()]

        # --- 2. Research them all (cap at 15 as a safety valve for unusual resumes) ---
        research_data = []
        for co in companies[:15]:
            info = get_company_research(co)
            if info:
                research_data.append(f"{co}: {info}")
        company_insight = "\n".join(research_data) if research_data else "No research available."
    except:
        company_insight = "No research available."

    # --- 3. Scoring ---
    requirements_str = "".join([f"- {r['requirement']} ({r['weight']}%)\n" for r in (weighted_requirements or [])])
    jd_str = f"Job Description:\n{job_description}\n\n" if job_description else ""

    # Build technical indicators context if available
    technical_context = ""
    if technical_indicators:
        technical_context += "\n\nTECHNICAL INDICATORS:\n"

        github_data = technical_indicators.get("github")
        if github_data:
            technical_context += "GitHub Profile:\n"
            technical_context += f"- Username: {github_data.get('username', 'N/A')}\n"
            technical_context += f"- Public repos: {github_data.get('public_repos', 0)}\n"
            technical_context += f"- Total stars received: {github_data.get('total_stars', 0)}\n"

            languages = github_data.get('languages', [])
            if languages:
                technical_context += f"- Top languages: {', '.join(languages)}\n"

            bio = github_data.get('bio', '')
            if bio:
                technical_context += f"- Bio: {bio}\n"

            followers = github_data.get('followers', 0)
            if followers > 0:
                technical_context += f"- Followers: {followers}\n"

        content_mentions = technical_indicators.get("content_mentions")
        if content_mentions:
            technical_context += "\nTechnical Content Creation:\n"

            if content_mentions.get("youtube"):
                technical_context += f"- YouTube: {len(content_mentions['youtube'])} mentions\n"
            if content_mentions.get("podcasts"):
                technical_context += f"- Podcasts: {len(content_mentions['podcasts'])} appearances\n"
            if content_mentions.get("articles"):
                technical_context += f"- Articles: {len(content_mentions['articles'])} mentions\n"
            if content_mentions.get("conferences"):
                technical_context += f"- Conferences: {len(content_mentions['conferences'])} talks\n"
            if content_mentions.get("news"):
                technical_context += f"- News coverage: {len(content_mentions['news'])} mentions\n"

        technical_context += "\nWhen evaluating:\n"
        technical_context += "1. Consider technical indicators as evidence of hands-on coding skills\n"
        technical_context += "2. Recent activity is more valuable than historical achievements\n"
        technical_context += "3. Senior leaders may have less direct coding but should show technical depth\n"
        technical_context += "4. Use job requirements to determine what 'hands-on' means for this specific role\n"

    today = datetime.now().strftime("%Y-%m-%d")
    today_context = f"\n\nTODAY'S DATE: {today}\nUse this date as the reference point for any \"in the past N years\" calculations.\n"

    # Build disqualifier instructions
    disqualifier_section = ""
    active_disqualifiers = [d.strip() for d in (disqualifiers or []) if d and d.strip()]
    if active_disqualifiers:
        disqualifier_section = "\n\nDISQUALIFIERS (any one of these makes the candidate automatically unfit):\n"
        for d in active_disqualifiers:
            disqualifier_section += f"- \"{d}\"\n"
        disqualifier_section += (
            "\nDisqualifier matching rules — be ACTIVELY LOOKING for evidence that any disqualifier is true:\n"
            "- Treat each disqualifier as a YES/NO question about the candidate's history. If the answer is plausibly YES based on the resume, FLAG IT.\n"
            "- For TIME-BASED conditions (e.g. \"has held a role in X in the past N years\"), the window is the past N years from TODAY'S DATE (above). "
            "Any role whose start or end date overlaps that window counts as YES.\n"
            "- For LOCATION conditions (e.g. \"role based in India\"), check the resume's stated city/country for each role. "
            "City names imply their country — a role with location \"Pune, India\" or just \"Bangalore\" or \"Mumbai\" or \"Hyderabad\" or \"Chennai\" or \"Delhi\" "
            "IS a role based in India. \"London\" implies UK, \"Toronto\" implies Canada, etc.\n"
            "- WORKED EXAMPLE: Resume shows \"TCS — Python Developer, Pune, India, June 2019 – Feb 2023\". "
            f"Today is {today}. The disqualifier is \"has held a role based in India in the past 6 years.\" "
            "6 years ago is roughly mid-2020. The TCS role ran 2019–Feb 2023, overlapping that window. "
            "Answer: YES, FLAG IT — set has_disqualifier=true, disqualifier_reason=\"has held a role based in India in the past 6 years (TCS, Pune, June 2019 – Feb 2023).\"\n"
            "- For CREDENTIAL conditions, check the education section.\n"
            "- If flagged, set \"has_disqualifier\": true and \"disqualifier_reason\": <exact disqualifier text> + (<short evidence from resume>). "
            "Otherwise set \"has_disqualifier\": false.\n"
            "- DO NOT require certainty. Reasonable inference from the resume is enough.\n"
        )

    # Build detailed requirements scoring instructions
    requirements_scoring = ""
    if weighted_requirements:
        requirements_scoring = "\n\nREQUIREMENT SCORING INSTRUCTIONS:\n"
        requirements_scoring += "For EACH requirement, use BINARY scoring — full weight or zero, no middle ground:\n\n"
        for r in weighted_requirements:
            req_text = r['requirement']
            req_weight = r['weight']
            requirements_scoring += f"- \"{req_text}\":\n"
            requirements_scoring += f"  * HAS the requirement: {req_weight} points\n"
            requirements_scoring += f"  * DOES NOT have it: 0 points\n\n"
        requirements_scoring += "HOW TO EVALUATE — there are TWO categories of requirements, treat them differently:\n\n"
        requirements_scoring += "CATEGORY A — LITERAL MATCH REQUIRED. Use this for:\n"
        requirements_scoring += "  - Job titles (e.g. \"held a title of Forward Deployed Engineer, Implementation Engineer, or Solutions Engineer\")\n"
        requirements_scoring += "  - Credentials and degrees (e.g. \"Master's in CS\", \"PMP certification\")\n"
        requirements_scoring += "  - Specific named technologies (e.g. \"Kubernetes\", \"Snowflake\")\n"
        requirements_scoring += "  - Quantitative thresholds (e.g. \"5+ years of Python\")\n"
        requirements_scoring += "  For Category A: the resume must EXPLICITLY contain the requirement text or a close paraphrase of the SAME concept.\n\n"
        requirements_scoring += "  *** CRITICAL ANTI-GAMING RULE FOR JOB TITLE REQUIREMENTS ***\n"
        requirements_scoring += "  Candidates often use AI to inject the job's target title into their resume's Summary, Objective, Headline, "
        requirements_scoring += "or self-description (e.g. \"Forward Deployed Engineer | 5 years experience\" as the top tagline) even though they\n"
        requirements_scoring += "  have never actually held that title in a real role. DO NOT be fooled by this.\n"
        requirements_scoring += "  - A title requirement matches ONLY if the title appears as the candidate's ACTUAL JOB TITLE in their work history "
        requirements_scoring += "(the Professional Experience / Work Experience / Employment History section), attached to a specific employer with dates.\n"
        requirements_scoring += "  - Cross-check against the employment_history you are extracting for this candidate: do any of the actual job titles "
        requirements_scoring += "you find there match the requirement? If NO, score the title requirement 0 — regardless of what the resume's Summary, "
        requirements_scoring += "Objective, Headline, About, Skills, or self-description sections claim.\n"
        requirements_scoring += "  - Example: Resume top says \"Forward Deployed Engineer with 5 years experience\" but work history shows \"AI/ML Engineer at Scale AI\" "
        requirements_scoring += "and \"Python Developer at TCS.\" → Score 0. The top label is keyword-stuffing, not employment history.\n"
        requirements_scoring += "  - Example: Work history shows \"Forward Deployed Engineer, Acme Inc., 2022 – 2024.\" → Score full credit. Real role.\n"
        requirements_scoring += "  - Example: requirement \"Forward Deployed Engineer\" + work history shows \"Senior Forward Deployed Engineer\" → Score full credit. "
        requirements_scoring += "Same title with a seniority modifier still counts.\n"
        requirements_scoring += "  *** END ANTI-GAMING RULE ***\n\n"
        requirements_scoring += "  Other Category A examples:\n"
        requirements_scoring += "  - requirement \"Forward Deployed Engineer\" + resume work history shows only \"AI/ML Engineer\" = 0 points. Different titles, no credit.\n"
        requirements_scoring += "  - requirement \"PhD\" + resume shows \"Master's\" = 0 points. Different credential.\n"
        requirements_scoring += "  - requirement \"5+ years Python\" + resume shows 3 years cumulative = 0 points. Doesn't meet threshold.\n\n"
        requirements_scoring += "CATEGORY B — INFERENCE FROM CONTEXT IS ALLOWED. Use this for:\n"
        requirements_scoring += "  - Industry / company type (e.g. \"experience at a B2B SaaS company\", \"fintech background\", \"healthcare experience\")\n"
        requirements_scoring += "  - Domain or sector exposure (e.g. \"worked on enterprise products\", \"consumer-facing\")\n"
        requirements_scoring += "  - General functional experience implied by role (e.g. \"led teams\", \"customer-facing role\")\n"
        requirements_scoring += "  For Category B, award full credit if ANY of the following is true:\n"
        requirements_scoring += "    (1) The candidate worked at a company you recognize (from the COMPANY RESEARCH context above or your general knowledge) that fits the description.\n"
        requirements_scoring += "        - Example: \"B2B SaaS\" + Scale AI = full credit.\n"
        requirements_scoring += "        - Example: \"fintech\" + Stripe = full credit.\n"
        requirements_scoring += "        - Example: \"big tech\" + Google = full credit.\n"
        requirements_scoring += "    (2) The resume EXPLICITLY states the qualification in a Summary, Skills, About, or job-description section, "
        requirements_scoring += "AND no company on the resume contradicts that claim. This handles candidates from small/unknown companies.\n"
        requirements_scoring += "        - Example: requirement \"fintech experience\" + resume summary says \"5 years building payments and lending platforms\" "
        requirements_scoring += "with employers you don't recognize = full credit (claim is explicit, nothing contradicts it).\n"
        requirements_scoring += "        - Counter-example: requirement \"fintech experience\" + resume claims fintech but every listed employer is "
        requirements_scoring += "clearly non-fintech (e.g. all furniture retailers, hospitals) = 0 (claim is contradicted by employer history).\n"
        requirements_scoring += "        - Counter-example: requirement \"fintech experience\" + resume makes no fintech claim anywhere and no listed "
        requirements_scoring += "company is fintech = 0 (nothing to support the claim).\n\n"
        requirements_scoring += "GENERAL RULES:\n"
        requirements_scoring += "- NO partial credit ever. Either full weight or zero.\n"
        requirements_scoring += "- For Category A: if you are not certain the literal claim is met, award 0.\n"
        requirements_scoring += "- For Category B: if a company in the resume plausibly matches the description, award full credit.\n"
        requirements_scoring += "- For each full-credit award, you must be able to point to a specific phrase in the resume (or a specific company from the resume) that justifies it.\n"

    # Build the prompt
    if technical_indicators:
        prompt = f"""Analyze this resume and score STRICTLY based on evidence.

{today_context}
COMPANY RESEARCH: {company_insight}

{technical_context}

{jd_str}WEIGHTED REQUIREMENTS:
{requirements_str}
{requirements_scoring}
{disqualifier_section}

Resume: {resume_text}

Return JSON with:
- overall_score: (0-100) Sum of all requirement scores
- requirement_scores: Object with each requirement text as key and its score as value
- strengths: List of candidate's strengths
- weaknesses: List of candidate's weaknesses
- summary: Brief overall assessment
- employment_history: Array of {{"company": "<exact company name as it appears in the resume>", "title": "<exact job title as it appears>", "dates": "<exact dates string as it appears, e.g. 'Mar 2024 - Present' or '2019-2023'"}} objects, one per role. Copy the strings VERBATIM from the resume so they can be located and highlighted in the original text.
- technical_indicators_analysis: Brief assessment of hands-on technical capabilities based on indicators provided

IMPORTANT: Your requirement_scores must add up to the overall_score. Score strictly based on actual evidence in the resume."""
    else:
        prompt = f"""Analyze this resume and score STRICTLY based on evidence.

{today_context}
COMPANY RESEARCH: {company_insight}

{jd_str}WEIGHTED REQUIREMENTS:
{requirements_str}
{requirements_scoring}
{disqualifier_section}

Resume: {resume_text}

Return JSON with:
- overall_score: (0-100) Sum of all requirement scores
- requirement_scores: Object with each requirement text as key and its score as value
- strengths: List of candidate's strengths
- weaknesses: List of candidate's weaknesses
- summary: Brief overall assessment
- employment_history: Array of {{"company": "<exact company name as it appears in the resume>", "title": "<exact job title as it appears>", "dates": "<exact dates string as it appears, e.g. 'Mar 2024 - Present' or '2019-2023'"}} objects, one per role. Copy the strings VERBATIM from the resume so they can be located and highlighted in the original text.

IMPORTANT: Your requirement_scores must add up to the overall_score. Score strictly based on actual evidence in the resume."""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception(is_rate_limit_error))
    def call_openai():
        # o4-mini is a reasoning model — it internally thinks step-by-step
        # before responding, which handles nuanced rules (anti-gaming title
        # checks, literal-vs-inferred categories, disqualifier evaluation)
        # better than gpt-4o. Note: reasoning models don't accept the
        # `temperature` parameter and instead use a fixed sampling strategy.
        response = openai_client.chat.completions.create(
            model="o4-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            reasoning_effort="medium",
        )
        return response.choices[0].message.content or "{}"
    
    try:
        result = json.loads(call_openai())
        raw_scores = result.get("requirement_scores") or {}

        # Server-side enforcement: snap every per-requirement score to BINARY.
        # Anything less than the requirement's full weight becomes 0. This is
        # the "all-or-nothing" rule the prompt asks for, hardened against
        # cases where the LLM still hedges with a partial number.
        if isinstance(raw_scores, dict) and weighted_requirements:
            cleaned_scores = {}
            total = 0.0
            for r in weighted_requirements:
                req_text = r.get("requirement", "")
                try:
                    weight = float(r.get("weight", 0) or 0)
                except (TypeError, ValueError):
                    weight = 0.0
                if not req_text:
                    continue

                # Look up the LLM's score for this requirement (exact key,
                # then case-insensitive, then substring of the first 30 chars).
                raw_value = raw_scores.get(req_text)
                if raw_value is None:
                    req_lc = req_text.strip().lower()
                    for k, v in raw_scores.items():
                        if isinstance(k, str) and k.strip().lower() == req_lc:
                            raw_value = v
                            break
                if raw_value is None:
                    prefix = req_text.strip()[:30].lower()
                    if prefix:
                        for k, v in raw_scores.items():
                            if isinstance(k, str) and prefix in k.strip().lower():
                                raw_value = v
                                break

                try:
                    score_val = float(raw_value) if raw_value is not None else 0.0
                except (TypeError, ValueError):
                    score_val = 0.0

                # Snap: full weight only if LLM returned at least the full weight.
                snapped = weight if score_val >= weight else 0.0
                cleaned_scores[req_text] = snapped
                total += snapped

            result["requirement_scores"] = cleaned_scores
            result["overall_score"] = total
        elif isinstance(raw_scores, dict) and raw_scores:
            # No requirements list to validate against — fall back to summing.
            total = 0.0
            for v in raw_scores.values():
                try:
                    total += float(v)
                except (TypeError, ValueError):
                    pass
            result["overall_score"] = total
        else:
            result["overall_score"] = float(result.get("overall_score") or 0)

        # Disqualifier override: if the LLM flagged a disqualifier, force score to 0
        if active_disqualifiers and result.get("has_disqualifier"):
            result["overall_score"] = 0
            if not result.get("disqualifier_reason"):
                result["disqualifier_reason"] = "Matched a disqualifier"

        return result
    except:
        return {"overall_score": 0, "summary": "Analysis error", "error": True}

def analyze_candidates_batch(candidates_with_resumes, job_description, weighted_requirements, jd_weight, require_hands_on_coding=False, progress_callback=None, disqualifiers=None):
    results = []

    # If hands-on coding filter is enabled, first enrich and filter candidates
    if require_hands_on_coding:
        from technical_enrichment import enrich_candidate_with_technical_indicators

        filtered_candidates = []
        for item in candidates_with_resumes:
            technical_indicators = enrich_candidate_with_technical_indicators(
                item["candidate"],
                item["resume_text"]
            )

            # Only include candidates with meaningful technical indicators
            if technical_indicators and has_strong_coding_indicators(technical_indicators):
                item["technical_indicators"] = technical_indicators
                filtered_candidates.append(item)

        candidates_with_resumes = filtered_candidates

    def process_candidate(item):
        technical_indicators = item.get("technical_indicators") if require_hands_on_coding else None

        analysis = analyze_single_resume(
            item["resume_text"],
            job_description,
            weighted_requirements,
            jd_weight,
            technical_indicators=technical_indicators,
            disqualifiers=disqualifiers
        )
        return {"candidate": item["candidate"], "analysis": analysis, "resume_text": item["resume_text"]}

    # max_workers=3 is safer when doing web searches to avoid being blocked
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(process_candidate, item): i for i, item in enumerate(candidates_with_resumes)}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except:
                failed_item = candidates_with_resumes[futures[future]]
                results.append({"candidate": failed_item["candidate"], "analysis": {"overall_score": 0}, "resume_text": failed_item.get("resume_text", "")})
            if progress_callback: progress_callback(len(results), len(candidates_with_resumes))

    results.sort(key=lambda x: x["analysis"].get("overall_score", 0), reverse=True)
    return results


def has_strong_coding_indicators(technical_indicators: dict) -> bool:
    """
    Determine if technical indicators show strong evidence of hands-on coding.

    Criteria:
    - Active GitHub profile with repos, OR
    - Technical content creation (articles, videos, podcasts, talks)

    Args:
        technical_indicators: Dict with github and/or content_mentions data

    Returns:
        True if candidate has strong coding indicators, False otherwise
    """
    if not technical_indicators:
        return False

    # Check GitHub activity
    github_data = technical_indicators.get("github")
    if github_data:
        public_repos = github_data.get("public_repos", 0)
        total_stars = github_data.get("total_stars", 0)

        # Has meaningful GitHub presence (repos or popular projects)
        if public_repos > 0 or total_stars > 0:
            return True

    # Check technical content creation
    content_mentions = technical_indicators.get("content_mentions")
    if content_mentions:
        # Has created any form of technical content
        total_mentions = sum(len(mentions) for mentions in content_mentions.values())
        if total_mentions > 0:
            return True

    return False