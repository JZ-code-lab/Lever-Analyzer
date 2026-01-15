"""
Technical Enrichment Module

This module provides functions to enrich candidate data with technical indicators:
- GitHub profile analysis (repos, stars, languages)
- Technical content mentions (YouTube, podcasts, articles, conference talks)

Used for the "Strong indication of recent hands-on coding skills" filter.
"""

import os
import re
import logging
import functools
import requests
from typing import Optional, Dict, List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

# GitHub API configuration
GITHUB_API_TOKEN = os.environ.get("GITHUB_API_TOKEN", "")
GITHUB_API_BASE = "https://api.github.com"
GITHUB_REQUEST_TIMEOUT = 5  # seconds


def is_rate_limit_error(exception: BaseException) -> bool:
    """Check if exception is a GitHub rate limit error."""
    error_msg = str(exception)
    return "403" in error_msg or "rate limit" in error_msg.lower()


def extract_github_urls(resume_text: str, candidate: dict) -> List[str]:
    """
    Extract GitHub URLs from resume text and candidate Lever profile.

    Args:
        resume_text: The candidate's resume text
        candidate: Candidate dict from Lever with links and urls fields

    Returns:
        List of GitHub URLs found (may be empty)
    """
    github_urls = []

    # Pattern to match GitHub URLs
    # Matches: github.com/username or github.com/username/repo
    github_pattern = r'https?://(?:www\.)?github\.com/([a-zA-Z0-9_-]+)(?:/[a-zA-Z0-9_.-]+)?'

    # Extract from resume text
    if resume_text:
        matches = re.finditer(github_pattern, resume_text, re.IGNORECASE)
        for match in matches:
            github_urls.append(match.group(0))

    # Extract from Lever candidate links
    if candidate:
        # Check 'links' field (list of URLs)
        links = candidate.get("links", [])
        for link in links:
            if isinstance(link, str) and "github.com" in link.lower():
                github_urls.append(link)

        # Check 'urls' field (dict with URL types)
        urls = candidate.get("urls", {})
        for url_type, url_value in urls.items():
            if isinstance(url_value, str) and "github.com" in url_value.lower():
                github_urls.append(url_value)

    # Remove duplicates while preserving order
    seen = set()
    unique_urls = []
    for url in github_urls:
        # Normalize URL (remove trailing slashes, convert to lowercase for comparison)
        normalized = url.rstrip('/').lower()
        if normalized not in seen:
            seen.add(normalized)
            unique_urls.append(url)

    return unique_urls


def extract_github_username(github_url: str) -> Optional[str]:
    """
    Extract username from a GitHub URL.

    Args:
        github_url: A GitHub URL (e.g., https://github.com/username)

    Returns:
        GitHub username or None if extraction fails
    """
    # Pattern to extract username from GitHub URL
    pattern = r'github\.com/([a-zA-Z0-9_-]+)'
    match = re.search(pattern, github_url, re.IGNORECASE)

    if match:
        username = match.group(1)
        # Filter out common non-username paths
        exclude_paths = ['about', 'features', 'pricing', 'enterprise', 'explore', 'topics', 'collections', 'trending', 'events', 'sponsors']
        if username.lower() not in exclude_paths:
            return username

    return None


@functools.lru_cache(maxsize=256)
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(is_rate_limit_error)
)
def fetch_github_profile(github_username: str) -> Optional[Dict]:
    """
    Fetch GitHub profile data for a user using GitHub REST API.

    Args:
        github_username: GitHub username

    Returns:
        Dict with profile data or None if fetch fails
        {
            "public_repos": int,
            "total_stars": int,
            "languages": [str],  # Top 3 languages
            "bio": str,
            "followers": int
        }
    """
    if not github_username:
        return None

    try:
        # Prepare headers with optional authentication
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Lever-Candidate-Analyzer"
        }
        if GITHUB_API_TOKEN:
            headers["Authorization"] = f"token {GITHUB_API_TOKEN}"

        # Fetch user profile
        user_url = f"{GITHUB_API_BASE}/users/{github_username}"
        user_response = requests.get(user_url, headers=headers, timeout=GITHUB_REQUEST_TIMEOUT)

        # Handle different response codes
        if user_response.status_code == 404:
            logging.info(f"GitHub user not found: {github_username}")
            return None
        elif user_response.status_code == 403:
            # Rate limit exceeded
            logging.warning(f"GitHub rate limit exceeded for user: {github_username}")
            raise Exception("GitHub rate limit exceeded")
        elif user_response.status_code != 200:
            logging.warning(f"GitHub API error {user_response.status_code} for user: {github_username}")
            return None

        user_data = user_response.json()

        # Extract basic profile info
        public_repos = user_data.get("public_repos", 0)
        bio = user_data.get("bio", "")
        followers = user_data.get("followers", 0)

        # Fetch repositories to get stars and languages
        repos_url = f"{GITHUB_API_BASE}/users/{github_username}/repos?sort=updated&per_page=100"
        repos_response = requests.get(repos_url, headers=headers, timeout=GITHUB_REQUEST_TIMEOUT)

        total_stars = 0
        language_bytes = {}

        if repos_response.status_code == 200:
            repos = repos_response.json()

            # Calculate total stars and aggregate languages
            for repo in repos:
                total_stars += repo.get("stargazers_count", 0)

                language = repo.get("language")
                if language:
                    # Use repo size as a proxy for language bytes (not perfect but simple)
                    size = repo.get("size", 0)
                    language_bytes[language] = language_bytes.get(language, 0) + size

        # Get top 3 languages by usage
        top_languages = sorted(language_bytes.keys(), key=lambda x: language_bytes[x], reverse=True)[:3]

        return {
            "public_repos": public_repos,
            "total_stars": total_stars,
            "languages": top_languages,
            "bio": bio or "",
            "followers": followers
        }

    except requests.Timeout:
        logging.warning(f"GitHub API timeout for user: {github_username}")
        return None
    except Exception as e:
        # Don't raise - gracefully degrade
        logging.warning(f"Error fetching GitHub profile for {github_username}: {e}")
        return None


def extract_technical_content_mentions(resume_text: str) -> Dict[str, List[str]]:
    """
    Extract mentions of technical content creation from resume text.

    Looks for:
    - YouTube videos/channels
    - Podcast appearances
    - Articles (Medium, Dev.to, Substack, etc.)
    - Conference talks/presentations
    - News coverage (TechCrunch, Forbes, etc.)

    Args:
        resume_text: The candidate's resume text

    Returns:
        Dict with categories and mentions:
        {
            "youtube": ["mention1", "mention2"],
            "podcasts": ["mention1"],
            "articles": ["mention1", "mention2"],
            "conferences": ["mention1"],
            "news": ["mention1"]
        }
    """
    if not resume_text:
        return {}

    mentions = {
        "youtube": [],
        "podcasts": [],
        "articles": [],
        "conferences": [],
        "news": []
    }

    # Convert to lowercase for case-insensitive matching
    text_lower = resume_text.lower()

    # YouTube patterns
    youtube_patterns = [
        r'youtube\.com/(?:watch\?v=|channel/|c/|user/)([^\s/\)]+)',
        r'youtu\.be/([^\s/\)]+)',
        r'youtube channel',
        r'youtube video',
        r'youtube creator'
    ]
    for pattern in youtube_patterns:
        matches = re.finditer(pattern, text_lower)
        for match in matches:
            # Extract surrounding context (up to 100 chars)
            start = max(0, match.start() - 50)
            end = min(len(resume_text), match.end() + 50)
            context = resume_text[start:end].strip()
            if context and context not in mentions["youtube"]:
                mentions["youtube"].append(context)

    # Podcast patterns
    podcast_patterns = [
        r'podcast (?:guest|appearance|episode|interview)',
        r'appeared on.*podcast',
        r'featured on.*podcast',
        r'invited to.*podcast'
    ]
    for pattern in podcast_patterns:
        matches = re.finditer(pattern, text_lower)
        for match in matches:
            start = max(0, match.start() - 30)
            end = min(len(resume_text), match.end() + 70)
            context = resume_text[start:end].strip()
            if context and context not in mentions["podcasts"]:
                mentions["podcasts"].append(context)

    # Article patterns (URLs and mentions)
    article_patterns = [
        r'medium\.com/@?([^\s/\)]+)',
        r'dev\.to/([^\s/\)]+)',
        r'substack\.com',
        r'published (?:article|post|blog)',
        r'wrote (?:article|post|blog|technical)',
        r'author of.*(?:article|post|blog)',
        r'technical (?:writer|writing|blog)'
    ]
    for pattern in article_patterns:
        matches = re.finditer(pattern, text_lower)
        for match in matches:
            start = max(0, match.start() - 30)
            end = min(len(resume_text), match.end() + 70)
            context = resume_text[start:end].strip()
            if context and context not in mentions["articles"]:
                mentions["articles"].append(context)

    # Conference patterns
    conference_patterns = [
        r'conference (?:speaker|talk|presentation)',
        r'presented at.*conference',
        r'keynote (?:speaker|at)',
        r'speaking at.*conference',
        r'speaker at',
        r'talked at'
    ]
    for pattern in conference_patterns:
        matches = re.finditer(pattern, text_lower)
        for match in matches:
            start = max(0, match.start() - 30)
            end = min(len(resume_text), match.end() + 70)
            context = resume_text[start:end].strip()
            if context and context not in mentions["conferences"]:
                mentions["conferences"].append(context)

    # News coverage patterns
    news_patterns = [
        r'techcrunch\.com',
        r'forbes\.com',
        r'featured in.*(?:techcrunch|forbes|wired|tech)',
        r'interviewed by.*(?:techcrunch|forbes|wired)',
        r'covered by.*(?:techcrunch|forbes|wired|tech)'
    ]
    for pattern in news_patterns:
        matches = re.finditer(pattern, text_lower)
        for match in matches:
            start = max(0, match.start() - 30)
            end = min(len(resume_text), match.end() + 70)
            context = resume_text[start:end].strip()
            if context and context not in mentions["news"]:
                mentions["news"].append(context)

    # Remove empty categories
    mentions = {k: v for k, v in mentions.items() if v}

    return mentions


def enrich_candidate_with_technical_indicators(candidate: dict, resume_text: str) -> Optional[Dict]:
    """
    Main enrichment function that gathers all technical indicators for a candidate.

    Args:
        candidate: Candidate dict from Lever
        resume_text: The candidate's resume text

    Returns:
        Dict with technical indicators or None if enrichment fails:
        {
            "github": {
                "username": str,
                "public_repos": int,
                "total_stars": int,
                "languages": [str],
                "bio": str,
                "followers": int
            },
            "content_mentions": {
                "youtube": [...],
                "podcasts": [...],
                "articles": [...],
                "conferences": [...],
                "news": [...]
            }
        }
    """
    try:
        indicators = {}

        # Extract and fetch GitHub profile
        github_urls = extract_github_urls(resume_text, candidate)
        if github_urls:
            # Try each URL until we get a valid profile
            for url in github_urls:
                username = extract_github_username(url)
                if username:
                    github_data = fetch_github_profile(username)
                    if github_data:
                        indicators["github"] = {
                            "username": username,
                            **github_data
                        }
                        break  # Found valid profile, stop searching

        # Extract technical content mentions
        content_mentions = extract_technical_content_mentions(resume_text)
        if content_mentions:
            indicators["content_mentions"] = content_mentions

        # Return indicators if we found anything
        return indicators if indicators else None

    except Exception as e:
        # Graceful degradation - never block the main analysis
        logging.warning(f"Error enriching candidate with technical indicators: {e}")
        return None
