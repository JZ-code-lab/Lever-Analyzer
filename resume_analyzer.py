import os
import json
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from openai import OpenAI

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")

# This is using Replit's AI Integrations service, which provides OpenAI-compatible API access
# without requiring your own OpenAI API key.
openai_client = OpenAI(
    api_key=AI_INTEGRATIONS_OPENAI_API_KEY,
    base_url=AI_INTEGRATIONS_OPENAI_BASE_URL
)


def is_rate_limit_error(exception: BaseException) -> bool:
    """Check if the exception is a rate limit or quota violation error."""
    error_msg = str(exception)
    return (
        "429" in error_msg
        or "RATELIMIT_EXCEEDED" in error_msg
        or "quota" in error_msg.lower()
        or "rate limit" in error_msg.lower()
        or (hasattr(exception, "status_code") and exception.status_code == 429)
    )


def analyze_single_resume(
    resume_text: str,
    job_description: Optional[str],
    weighted_requirements: list[dict],
    jd_weight: float
) -> dict:
    """
    Analyze a single resume against job description and weighted requirements.
    Returns analysis with score, strengths, and weaknesses.
    """
    
    requirements_str = ""
    if weighted_requirements:
        requirements_str = "Weighted Requirements:\n"
        for req in weighted_requirements:
            requirements_str += f"- {req['requirement']} (Weight: {req['weight']}%)\n"
    
    jd_str = ""
    if job_description and job_description.strip():
        jd_str = f"Job Description:\n{job_description}\n\n"
    
    scoring_instructions = ""
    if job_description and job_description.strip() and weighted_requirements:
        req_weight = 100 - jd_weight
        scoring_instructions = f"""
Scoring Breakdown:
- Job Description Match: {jd_weight}% of total score
- Weighted Requirements Match: {req_weight}% of total score

For the requirements portion, score each requirement based on how well the candidate meets it,
then calculate the weighted average using the provided weights.
"""
    elif job_description and job_description.strip():
        scoring_instructions = "Score based entirely on how well the candidate matches the job description."
    elif weighted_requirements:
        scoring_instructions = "Score based entirely on the weighted requirements."
    else:
        scoring_instructions = "Provide a general assessment of the candidate's qualifications."
    
    prompt = f"""Analyze this resume against the provided criteria and provide a detailed assessment.

{jd_str}{requirements_str}

{scoring_instructions}

Resume:
{resume_text}

Provide your analysis in the following JSON format:
{{
    "overall_score": <number between 0 and 100>,
    "strengths": [<list of 3-5 key strengths>],
    "weaknesses": [<list of 2-4 areas of concern or gaps>],
    "requirement_scores": {{<requirement: score for each weighted requirement if applicable>}},
    "jd_match_score": <score for job description match if applicable>,
    "summary": "<2-3 sentence summary of the candidate's fit>"
}}

Be objective and thorough in your analysis."""

    @retry(
        stop=stop_after_attempt(7),
        wait=wait_exponential(multiplier=1, min=2, max=128),
        retry=retry_if_exception(is_rate_limit_error),
        reraise=True
    )
    def call_openai():
        # the newest OpenAI model is "gpt-5" which was released August 7, 2025.
        # do not change this unless explicitly requested by the user
        response = openai_client.chat.completions.create(
            model="gpt-5",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_completion_tokens=2048
        )
        return response.choices[0].message.content or "{}"
    
    try:
        result = call_openai()
        return json.loads(result)
    except Exception as e:
        return {
            "overall_score": 0,
            "strengths": [],
            "weaknesses": ["Error analyzing resume"],
            "summary": f"Analysis failed: {str(e)}",
            "error": True
        }


def analyze_candidates_batch(
    candidates_with_resumes: list[dict],
    job_description: Optional[str],
    weighted_requirements: list[dict],
    jd_weight: float,
    progress_callback=None
) -> list[dict]:
    """
    Analyze multiple candidates concurrently.
    Each item in candidates_with_resumes should have:
    - candidate: the candidate dict from Lever
    - resume_text: the parsed resume text
    """
    
    results = []
    total = len(candidates_with_resumes)
    completed = 0
    
    def process_candidate(item: dict) -> dict:
        candidate = item["candidate"]
        resume_text = item["resume_text"]
        
        analysis = analyze_single_resume(
            resume_text=resume_text,
            job_description=job_description,
            weighted_requirements=weighted_requirements,
            jd_weight=jd_weight
        )
        
        return {
            "candidate": candidate,
            "analysis": analysis
        }
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(process_candidate, item): i 
            for i, item in enumerate(candidates_with_resumes)
        }
        
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                idx = futures[future]
                candidate = candidates_with_resumes[idx]["candidate"]
                results.append({
                    "candidate": candidate,
                    "analysis": {
                        "overall_score": 0,
                        "strengths": [],
                        "weaknesses": ["Error during analysis"],
                        "summary": f"Analysis failed: {str(e)}",
                        "error": True
                    }
                })
            
            completed += 1
            if progress_callback:
                progress_callback(completed, total)
    
    results.sort(key=lambda x: x["analysis"].get("overall_score", 0), reverse=True)
    
    return results
