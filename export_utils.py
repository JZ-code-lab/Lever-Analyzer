import pandas as pd
from io import StringIO
from lever_client import (
    get_candidate_name,
    get_candidate_email,
    get_candidate_linkedin,
    get_candidate_lever_url
)


def export_results_to_csv(results: list[dict]) -> str:
    """
    Export analysis results to CSV format with Excel HYPERLINK formulas.

    Args:
        results: List of result dictionaries with 'candidate' and 'analysis' keys

    Returns:
        CSV string ready for download
    """
    rows = []

    for rank, result in enumerate(results, 1):
        candidate = result["candidate"]
        analysis = result["analysis"]

        # Extract basic candidate info
        name = get_candidate_name(candidate)
        email = get_candidate_email(candidate) or ""
        linkedin_url = get_candidate_linkedin(candidate)
        lever_url = get_candidate_lever_url(candidate)

        # Get analysis data
        overall_score = analysis.get("overall_score", 0)
        summary = analysis.get("summary", "")

        # Format strengths and weaknesses as bullet lists
        strengths = analysis.get("strengths", [])
        strengths_text = "; ".join(strengths) if isinstance(strengths, list) else str(strengths)

        weaknesses = analysis.get("weaknesses", [])
        weaknesses_text = "; ".join(weaknesses) if isinstance(weaknesses, list) else str(weaknesses)

        # Get requirement scores
        req_scores = analysis.get("requirement_scores", {})
        req_scores_text = "; ".join([f"{req}: {score}" for req, score in req_scores.items()]) if req_scores else ""

        jd_match_score = analysis.get("jd_match_score", "")

        # Get posting name if available
        posting_name = candidate.get("_posting_name", "")

        # Create hyperlink formulas for Excel/Google Sheets
        lever_hyperlink = f'=HYPERLINK("{lever_url}", "View Profile")' if lever_url else ""
        linkedin_hyperlink = f'=HYPERLINK("{linkedin_url}", "View LinkedIn")' if linkedin_url else ""

        row = {
            "Rank": rank,
            "Name": name,
            "Email": email,
            "Overall Score": overall_score,
            "Position": posting_name,
            "Summary": summary,
            "Strengths": strengths_text,
            "Weaknesses": weaknesses_text,
            "JD Match Score": jd_match_score,
            "Requirement Scores": req_scores_text,
            "Lever Profile": lever_hyperlink,
            "LinkedIn Profile": linkedin_hyperlink,
        }

        rows.append(row)

    # Create DataFrame
    df = pd.DataFrame(rows)

    # Convert to CSV
    # Important: Use quoting to preserve formulas
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False, quoting=1)  # quoting=1 is QUOTE_ALL

    return csv_buffer.getvalue()


def filter_results_by_score(results: list[dict], minimum_score: int) -> list[dict]:
    """
    Filter results by minimum score threshold.

    Args:
        results: List of result dictionaries
        minimum_score: Minimum score threshold (0-100)

    Returns:
        Filtered list of results
    """
    if minimum_score <= 0:
        return results

    return [
        result for result in results
        if result["analysis"].get("overall_score", 0) >= minimum_score
    ]
