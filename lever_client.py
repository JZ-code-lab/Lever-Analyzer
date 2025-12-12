import os
import requests
from typing import Optional
import pdfplumber
from io import BytesIO
import base64

LEVER_API_KEY = os.environ.get("LEVER_API_KEY", "")
LEVER_API_BASE = "https://api.lever.co/v1"


def get_auth_header() -> dict:
    """Get the authorization header for Lever API requests."""
    credentials = base64.b64encode(f"{LEVER_API_KEY}:".encode()).decode()
    return {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json"
    }


def fetch_all_postings() -> list[dict]:
    """Fetch all open and closed postings from Lever."""
    postings = []
    offset = None
    
    while True:
        params = {"limit": 100, "mode": "all"}
        if offset:
            params["offset"] = offset
            
        response = requests.get(
            f"{LEVER_API_BASE}/postings",
            headers=get_auth_header(),
            params=params
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to fetch postings: {response.text}")
        
        data = response.json()
        postings.extend(data.get("data", []))
        
        if not data.get("hasNext"):
            break
        offset = data.get("next")
    
    return postings


def fetch_candidates_for_posting(posting_id: str) -> list[dict]:
    """Fetch all candidates for a specific posting, excluding archived."""
    candidates = []
    offset = None
    
    while True:
        params = {
            "posting_id": posting_id,
            "limit": 100
        }
        if offset:
            params["offset"] = offset
            
        response = requests.get(
            f"{LEVER_API_BASE}/opportunities",
            headers=get_auth_header(),
            params=params
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to fetch candidates: {response.text}")
        
        data = response.json()
        
        for candidate in data.get("data", []):
            if not candidate.get("archived"):
                candidates.append(candidate)
        
        if not data.get("hasNext"):
            break
        offset = data.get("next")
    
    return candidates


def fetch_candidate_resumes(opportunity_id: str) -> list[dict]:
    """Fetch resume files for a candidate opportunity."""
    response = requests.get(
        f"{LEVER_API_BASE}/opportunities/{opportunity_id}/resumes",
        headers=get_auth_header()
    )
    
    if response.status_code != 200:
        return []
    
    return response.json().get("data", [])


def download_and_parse_resume(file_download_url: str) -> Optional[str]:
    """Download a resume file and extract text content."""
    try:
        response = requests.get(
            file_download_url,
            headers=get_auth_header()
        )
        
        if response.status_code != 200:
            return None
        
        content_type = response.headers.get("Content-Type", "")
        
        if "pdf" in content_type.lower() or file_download_url.lower().endswith(".pdf"):
            with pdfplumber.open(BytesIO(response.content)) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text.strip() if text else None
        else:
            return response.text
            
    except Exception as e:
        print(f"Error parsing resume: {e}")
        return None


def get_candidate_linkedin(candidate: dict) -> Optional[str]:
    """Extract LinkedIn URL from candidate data."""
    links = candidate.get("links", [])
    for link in links:
        if "linkedin" in link.lower():
            return link
    
    urls = candidate.get("urls", {})
    if isinstance(urls, dict):
        linkedin = urls.get("linkedin")
        if linkedin:
            return linkedin
    
    return None


def get_candidate_lever_url(candidate: dict) -> str:
    """Generate the Lever profile URL for a candidate."""
    opportunity_id = candidate.get("id", "")
    return f"https://hire.lever.co/candidates/{opportunity_id}"


def get_candidate_name(candidate: dict) -> str:
    """Get the candidate's name."""
    return candidate.get("name", "Unknown Candidate")


def get_candidate_email(candidate: dict) -> Optional[str]:
    """Get the candidate's email."""
    emails = candidate.get("emails", [])
    return emails[0] if emails else None


def get_resume_text_for_candidate(opportunity_id: str) -> Optional[str]:
    """Get parsed resume text for a candidate."""
    resumes = fetch_candidate_resumes(opportunity_id)
    
    for resume in resumes:
        file_info = resume.get("file", {})
        download_url = file_info.get("downloadUrl")
        
        if download_url:
            text = download_and_parse_resume(download_url)
            if text:
                return text
    
    return None
