import streamlit as st
import os
from lever_client import (
    fetch_all_postings,
    fetch_candidates_for_posting,
    get_resume_text_for_candidate,
    get_candidate_name,
    get_candidate_email,
    get_candidate_linkedin,
    get_candidate_lever_url
)
from resume_analyzer import analyze_candidates_batch

st.set_page_config(
    page_title="Lever Analyzer",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Lever Analyzer")
st.markdown("Analyze and rank candidates from Lever positions using AI-powered resume analysis.")

if "postings" not in st.session_state:
    st.session_state.postings = None
if "selected_posting" not in st.session_state:
    st.session_state.selected_posting = None
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None
if "requirements" not in st.session_state:
    st.session_state.requirements = [{"requirement": "", "weight": 20}]

lever_api_key = os.environ.get("LEVER_API_KEY", "")

if not lever_api_key:
    st.error("⚠️ LEVER_API_KEY environment variable is not set. Please add your Lever API key to continue.")
    st.stop()

with st.sidebar:
    st.header("Configuration")
    
    if st.button("🔄 Refresh Positions", use_container_width=True):
        st.session_state.postings = None
        st.session_state.analysis_results = None
    
    st.divider()
    
    st.subheader("Weighted Requirements")
    st.caption("Add requirements and assign weights (must total 100%)")
    
    total_weight = 0
    requirements_to_remove = []
    
    for i, req in enumerate(st.session_state.requirements):
        col1, col2, col3 = st.columns([3, 1, 0.5])
        with col1:
            st.session_state.requirements[i]["requirement"] = st.text_input(
                f"Requirement {i+1}",
                value=req["requirement"],
                key=f"req_{i}",
                label_visibility="collapsed",
                placeholder="e.g., 5+ years Python experience"
            )
        with col2:
            st.session_state.requirements[i]["weight"] = st.number_input(
                f"Weight {i+1}",
                min_value=0,
                max_value=100,
                value=req["weight"],
                key=f"weight_{i}",
                label_visibility="collapsed"
            )
        with col3:
            if st.button("❌", key=f"remove_{i}"):
                requirements_to_remove.append(i)
        
        total_weight += st.session_state.requirements[i]["weight"]
    
    for i in reversed(requirements_to_remove):
        st.session_state.requirements.pop(i)
    
    if st.button("➕ Add Requirement", use_container_width=True):
        st.session_state.requirements.append({"requirement": "", "weight": 0})
        st.rerun()
    
    valid_requirements = [r for r in st.session_state.requirements if r["requirement"].strip()]
    if valid_requirements:
        if total_weight != 100:
            st.warning(f"⚠️ Weights total {total_weight}% (should be 100%)")
        else:
            st.success("✅ Weights total 100%")
    
    st.divider()
    
    st.subheader("Scoring Balance")
    jd_weight = st.slider(
        "Job Description vs Requirements",
        min_value=0,
        max_value=100,
        value=50,
        help="How much weight to give job description (left) vs weighted requirements (right)"
    )
    st.caption(f"Job Description: {jd_weight}% | Requirements: {100-jd_weight}%")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Select Position")
    
    if st.session_state.postings is None:
        with st.spinner("Loading positions from Lever..."):
            try:
                st.session_state.postings = fetch_all_postings()
            except Exception as e:
                st.error(f"Failed to load positions: {str(e)}")
                st.session_state.postings = []
    
    postings = st.session_state.postings
    
    if postings:
        posting_options = {
            f"{p.get('text', 'Untitled')} ({p.get('state', 'unknown')})": p 
            for p in postings
        }
        
        selected_option = st.selectbox(
            "Choose a position",
            options=[""] + list(posting_options.keys()),
            help="Start typing to filter positions"
        )
        
        if selected_option:
            st.session_state.selected_posting = posting_options[selected_option]
            posting = st.session_state.selected_posting
            
            st.markdown("**Position Details:**")
            st.write(f"**Title:** {posting.get('text', 'N/A')}")
            st.write(f"**State:** {posting.get('state', 'N/A')}")
            st.write(f"**Team:** {posting.get('categories', {}).get('team', 'N/A')}")
            st.write(f"**Location:** {posting.get('categories', {}).get('location', 'N/A')}")
    else:
        st.info("No positions found in Lever.")

with col2:
    st.subheader("Job Description (Optional)")
    job_description = st.text_area(
        "Paste or enter a custom job description",
        height=250,
        help="Leave blank to score based only on weighted requirements",
        placeholder="Paste the full job description here, or leave empty to use only the weighted requirements for scoring..."
    )

st.divider()

if st.session_state.selected_posting:
    posting = st.session_state.selected_posting
    
    if st.button("🔍 Analyze Candidates", type="primary", use_container_width=True):
        valid_reqs = [r for r in st.session_state.requirements if r["requirement"].strip()]
        
        if not valid_reqs and not job_description.strip():
            st.error("Please provide either weighted requirements or a job description to analyze candidates.")
        else:
            posting_id = posting.get("id")
            
            with st.spinner("Fetching candidates from Lever..."):
                try:
                    candidates = fetch_candidates_for_posting(posting_id)
                except Exception as e:
                    st.error(f"Failed to fetch candidates: {str(e)}")
                    candidates = []
            
            if not candidates:
                st.warning("No active candidates found for this position.")
            else:
                st.info(f"Found {len(candidates)} candidates. Fetching resumes...")
                
                candidates_with_resumes = []
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, candidate in enumerate(candidates):
                    status_text.text(f"Fetching resume {i+1}/{len(candidates)}: {get_candidate_name(candidate)}")
                    
                    resume_text = get_resume_text_for_candidate(candidate.get("id"))
                    
                    if resume_text:
                        candidates_with_resumes.append({
                            "candidate": candidate,
                            "resume_text": resume_text
                        })
                    
                    progress_bar.progress((i + 1) / len(candidates))
                
                progress_bar.empty()
                status_text.empty()
                
                if not candidates_with_resumes:
                    st.warning("No resumes found for any candidates.")
                else:
                    st.info(f"Analyzing {len(candidates_with_resumes)} candidates with resumes...")
                    
                    analysis_progress = st.progress(0)
                    analysis_status = st.empty()
                    
                    def update_progress(completed, total):
                        analysis_progress.progress(completed / total)
                        analysis_status.text(f"Analyzed {completed}/{total} candidates")
                    
                    try:
                        results = analyze_candidates_batch(
                            candidates_with_resumes=candidates_with_resumes,
                            job_description=job_description if job_description.strip() else None,
                            weighted_requirements=valid_reqs,
                            jd_weight=jd_weight,
                            progress_callback=update_progress
                        )
                        
                        st.session_state.analysis_results = results
                        analysis_progress.empty()
                        analysis_status.empty()
                        
                    except Exception as e:
                        st.error(f"Analysis failed: {str(e)}")
                        analysis_progress.empty()
                        analysis_status.empty()

if st.session_state.analysis_results:
    st.divider()
    st.header("📈 Candidate Rankings")
    
    results = st.session_state.analysis_results
    
    for rank, result in enumerate(results, 1):
        candidate = result["candidate"]
        analysis = result["analysis"]
        
        score = analysis.get("overall_score", 0)
        
        if score >= 80:
            score_color = "🟢"
        elif score >= 60:
            score_color = "🟡"
        else:
            score_color = "🔴"
        
        name = get_candidate_name(candidate)
        email = get_candidate_email(candidate)
        linkedin = get_candidate_linkedin(candidate)
        lever_url = get_candidate_lever_url(candidate)
        
        with st.expander(f"#{rank} {score_color} **{name}** - Score: {score}/100", expanded=(rank <= 3)):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("**Summary:**")
                st.write(analysis.get("summary", "No summary available"))
                
                st.markdown("**Strengths:**")
                strengths = analysis.get("strengths", [])
                for strength in strengths:
                    st.markdown(f"✅ {strength}")
                
                st.markdown("**Weaknesses:**")
                weaknesses = analysis.get("weaknesses", [])
                for weakness in weaknesses:
                    st.markdown(f"⚠️ {weakness}")
            
            with col2:
                st.markdown("**Score Breakdown:**")
                st.metric("Overall Score", f"{score}/100")
                
                if analysis.get("jd_match_score") is not None:
                    st.write(f"JD Match: {analysis.get('jd_match_score')}/100")
                
                req_scores = analysis.get("requirement_scores", {})
                if req_scores:
                    st.markdown("**Requirement Scores:**")
                    for req, req_score in req_scores.items():
                        st.write(f"• {req[:30]}...: {req_score}")
                
                st.divider()
                
                st.markdown("**Links:**")
                st.markdown(f"[📋 Lever Profile]({lever_url})")
                
                if linkedin:
                    st.markdown(f"[💼 LinkedIn]({linkedin})")
                
                if email:
                    st.write(f"📧 {email}")

st.divider()
st.caption("Lever Analyzer - AI-powered candidate ranking and analysis")
