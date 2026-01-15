import os
import json
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

def analyze_single_resume(resume_text: str, job_description: Optional[str], weighted_requirements: list[dict], jd_weight: float, technical_indicators: Optional[dict] = None) -> dict:
    # --- 1. Extract Top 2 Companies ---
    try:
        name_extract = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": f"List the 2 most recent unique employers from this resume. Return ONLY company names separated by a comma.\n\n{resume_text[:1500]}"}]
        )
        companies = [c.strip() for c in name_extract.choices[0].message.content.split(",")]
        
        # --- 2. Research Them ---
        research_data = []
        for co in companies[:2]: # Safety limit to 2
            info = get_company_research(co)
            if info:
                research_data.append(f"{co}: {info}")
        company_insight = "\n".join(research_data)
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

    # Build detailed requirements scoring instructions
    requirements_scoring = ""
    if weighted_requirements:
        requirements_scoring = "\n\nREQUIREMENT SCORING INSTRUCTIONS:\n"
        requirements_scoring += "For EACH requirement, you MUST score proportionally based on actual evidence:\n\n"
        for r in weighted_requirements:
            req_text = r['requirement']
            req_weight = r['weight']
            requirements_scoring += f"- \"{req_text}\" (max {req_weight} points):\n"
            requirements_scoring += f"  * Full match (100%): {req_weight} points\n"
            requirements_scoring += f"  * Strong match (75%): {int(req_weight * 0.75)} points\n"
            requirements_scoring += f"  * Moderate match (50%): {int(req_weight * 0.50)} points\n"
            requirements_scoring += f"  * Weak match (25%): {int(req_weight * 0.25)} points\n"
            requirements_scoring += f"  * Very limited/no evidence (0-10%): 0-{int(req_weight * 0.10)} points\n\n"
        requirements_scoring += "CRITICAL SCORING RULES:\n"
        requirements_scoring += "- If you note 'very limited', 'minimal', or 'no documented' experience, score must be 0-10% of max (not 80%!)\n"
        requirements_scoring += "- If you note 'some' or 'limited' experience, score should be 25-50% of max\n"
        requirements_scoring += "- Only give 75-100% if candidate clearly demonstrates strong or extensive experience\n"
        requirements_scoring += "- Be strict and honest - partial experience = partial score\n"

    # Build the prompt
    if technical_indicators:
        prompt = f"""Analyze this resume and score STRICTLY based on evidence.

COMPANY RESEARCH: {company_insight}

{technical_context}

{jd_str}WEIGHTED REQUIREMENTS:
{requirements_str}
{requirements_scoring}

Resume: {resume_text}

Return JSON with:
- overall_score: (0-100) Sum of all requirement scores
- requirement_scores: Object with each requirement text as key and its score as value
- strengths: List of candidate's strengths
- weaknesses: List of candidate's weaknesses
- summary: Brief overall assessment
- technical_indicators_analysis: Brief assessment of hands-on technical capabilities based on indicators provided

IMPORTANT: Your requirement_scores must add up to the overall_score. Score strictly based on actual evidence in the resume."""
    else:
        prompt = f"""Analyze this resume and score STRICTLY based on evidence.

COMPANY RESEARCH: {company_insight}

{jd_str}WEIGHTED REQUIREMENTS:
{requirements_str}
{requirements_scoring}

Resume: {resume_text}

Return JSON with:
- overall_score: (0-100) Sum of all requirement scores
- requirement_scores: Object with each requirement text as key and its score as value
- strengths: List of candidate's strengths
- weaknesses: List of candidate's weaknesses
- summary: Brief overall assessment

IMPORTANT: Your requirement_scores must add up to the overall_score. Score strictly based on actual evidence in the resume."""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception(is_rate_limit_error))
    def call_openai():
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content or "{}"
    
    try:
        result = json.loads(call_openai())
        result["overall_score"] = float(result.get("overall_score") or 0)
        return result
    except:
        return {"overall_score": 0, "summary": "Analysis error", "error": True}

def analyze_candidates_batch(candidates_with_resumes, job_description, weighted_requirements, jd_weight, require_hands_on_coding=False, progress_callback=None):
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
            technical_indicators=technical_indicators
        )
        return {"candidate": item["candidate"], "analysis": analysis}

    # max_workers=3 is safer when doing web searches to avoid being blocked
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(process_candidate, item): i for i, item in enumerate(candidates_with_resumes)}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except:
                results.append({"candidate": candidates_with_resumes[futures[future]]["candidate"], "analysis": {"overall_score": 0}})
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