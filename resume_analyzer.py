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

    # Build the prompt
    if technical_indicators:
        prompt = f"""Analyze this resume.
    COMPANY RESEARCH: {company_insight}
    {technical_context}
    {jd_str}{requirements_str}
    Resume: {resume_text}
    Return JSON with: overall_score (0-100), strengths, weaknesses, summary, technical_indicators_analysis (brief assessment of hands-on technical capabilities based on indicators provided)."""
    else:
        prompt = f"""Analyze this resume.
    COMPANY RESEARCH: {company_insight}
    {jd_str}{requirements_str}
    Resume: {resume_text}
    Return JSON with: overall_score (0-100), strengths, weaknesses, summary."""

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
    def process_candidate(item):
        technical_indicators = None

        # If hands-on coding filter enabled, enrich with technical indicators
        if require_hands_on_coding:
            from technical_enrichment import enrich_candidate_with_technical_indicators
            technical_indicators = enrich_candidate_with_technical_indicators(
                item["candidate"],
                item["resume_text"]
            )

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