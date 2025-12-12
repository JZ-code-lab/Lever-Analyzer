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

if "postings" not in st.session_state:
    st.session_state.postings = None
if "selected_posting" not in st.session_state:
    st.session_state.selected_posting = None
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None
if "requirements" not in st.session_state:
    st.session_state.requirements = [{"requirement": "", "weight": 25}, {"requirement": "", "weight": 25}, {"requirement": "", "weight": 25}, {"requirement": "", "weight": 25}]
if "current_step" not in st.session_state:
    st.session_state.current_step = 1
if "job_description" not in st.session_state:
    st.session_state.job_description = ""
if "jd_weight" not in st.session_state:
    st.session_state.jd_weight = 50

lever_api_key = os.environ.get("LEVER_API_KEY", "")

if not lever_api_key:
    st.error("Missing LEVER_API_KEY. Please add your Lever API key to continue.")
    st.stop()

st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0 2rem 0;
    }
    .step-container {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 2rem;
        margin: 1rem 0;
    }
    .step-header {
        font-size: 1.3rem;
        font-weight: 600;
        margin-bottom: 1rem;
        color: #1f2937;
    }
    .weight-meter {
        height: 8px;
        background-color: #e5e7eb;
        border-radius: 4px;
        overflow: hidden;
        margin: 0.5rem 0;
    }
    .stButton > button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">', unsafe_allow_html=True)
st.title("📊 Lever Analyzer")
st.caption("AI-powered candidate ranking and analysis for your Lever positions")
st.markdown('</div>', unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    step_cols = st.columns(3)
    for i, step_col in enumerate(step_cols, 1):
        with step_col:
            if i < st.session_state.current_step:
                st.success(f"Step {i} ✓")
            elif i == st.session_state.current_step:
                st.info(f"Step {i}")
            else:
                st.markdown(f"Step {i}")

st.divider()

if st.session_state.analysis_results:
    if st.button("← Start New Analysis", type="secondary"):
        st.session_state.analysis_results = None
        st.session_state.current_step = 1
        st.session_state.selected_posting = None
        st.rerun()
    
    st.header("📈 Candidate Rankings")
    st.caption(f"Position: {st.session_state.selected_posting.get('text', 'Unknown')}")
    
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
                        display_req = req[:30] + "..." if len(req) > 30 else req
                        st.write(f"• {display_req}: {req_score}")
                
                st.divider()
                
                st.markdown("**Links:**")
                st.markdown(f"[📋 Lever Profile]({lever_url})")
                
                if linkedin:
                    st.markdown(f"[💼 LinkedIn]({linkedin})")
                
                if email:
                    st.write(f"📧 {email}")

elif st.session_state.current_step == 1:
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col2:
        st.markdown("### Step 1: Select Position")
        st.caption("Choose a Lever position to analyze candidates")
        
        if st.session_state.postings is None:
            with st.spinner("Loading positions from Lever..."):
                try:
                    st.session_state.postings = fetch_all_postings()
                except Exception as e:
                    st.error(f"Failed to load positions: {str(e)}")
                    st.session_state.postings = []
        
        postings = st.session_state.postings
        
        if postings:
            col_refresh, col_count = st.columns([1, 3])
            with col_refresh:
                if st.button("🔄 Refresh"):
                    st.session_state.postings = None
                    st.rerun()
            with col_count:
                st.caption(f"{len(postings)} positions found")
            
            posting_options = {
                f"{p.get('text', 'Untitled')} ({p.get('state', 'unknown')})": p 
                for p in postings
            }
            
            selected_option = st.selectbox(
                "Search and select a position",
                options=[""] + list(posting_options.keys()),
                help="Start typing to filter positions",
                label_visibility="collapsed",
                placeholder="Type to search positions..."
            )
            
            if selected_option:
                st.session_state.selected_posting = posting_options[selected_option]
                posting = st.session_state.selected_posting
                
                st.markdown("---")
                st.markdown("**Position Details:**")
                detail_col1, detail_col2 = st.columns(2)
                with detail_col1:
                    st.write(f"**Title:** {posting.get('text', 'N/A')}")
                    st.write(f"**State:** {posting.get('state', 'N/A')}")
                with detail_col2:
                    st.write(f"**Team:** {posting.get('categories', {}).get('team', 'N/A')}")
                    st.write(f"**Location:** {posting.get('categories', {}).get('location', 'N/A')}")
                
                st.markdown("---")
                st.markdown("**Job Description (Optional)**")
                st.caption("Add a custom job description to factor into candidate scoring")
                st.session_state.job_description = st.text_area(
                    "Job Description",
                    value=st.session_state.job_description,
                    height=150,
                    placeholder="Paste the job description here, or leave empty to use only weighted requirements...",
                    label_visibility="collapsed"
                )
                
                st.markdown("")
                if st.button("Continue to Requirements →", type="primary", use_container_width=True):
                    st.session_state.current_step = 2
                    st.rerun()
        else:
            st.warning("No positions found in Lever. Check your API key or try refreshing.")

elif st.session_state.current_step == 2:
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col2:
        if st.button("← Back to Position Selection"):
            st.session_state.current_step = 1
            st.rerun()
        
        st.markdown("### Step 2: Define Requirements")
        st.caption(f"Position: {st.session_state.selected_posting.get('text', 'Unknown')}")
        
        st.markdown("---")
        st.markdown("**Weighted Requirements**")
        st.caption("Define what you're looking for in candidates. Weights should total 100%.")
        
        total_weight = 0
        requirements_to_remove = []
        
        for i, req in enumerate(st.session_state.requirements):
            req_col1, req_col2, req_col3 = st.columns([5, 1, 0.5])
            with req_col1:
                st.session_state.requirements[i]["requirement"] = st.text_input(
                    f"Requirement {i+1}",
                    value=req["requirement"],
                    key=f"req_{i}",
                    label_visibility="collapsed",
                    placeholder=f"e.g., 5+ years Python experience"
                )
            with req_col2:
                st.session_state.requirements[i]["weight"] = st.number_input(
                    f"Weight {i+1}",
                    min_value=0,
                    max_value=100,
                    value=req["weight"],
                    key=f"weight_{i}",
                    label_visibility="collapsed"
                )
            with req_col3:
                if len(st.session_state.requirements) > 1:
                    if st.button("✕", key=f"remove_{i}"):
                        requirements_to_remove.append(i)
            
            total_weight += st.session_state.requirements[i]["weight"]
        
        for i in reversed(requirements_to_remove):
            st.session_state.requirements.pop(i)
            st.rerun()
        
        add_col1, add_col2 = st.columns([3, 1])
        with add_col1:
            if st.button("+ Add Requirement"):
                st.session_state.requirements.append({"requirement": "", "weight": 0})
                st.rerun()
        
        valid_requirements = [r for r in st.session_state.requirements if r["requirement"].strip()]
        valid_weight = sum(r["weight"] for r in valid_requirements)
        
        st.markdown("---")
        
        weight_col1, weight_col2 = st.columns([2, 1])
        with weight_col1:
            st.progress(min(valid_weight, 100) / 100)
        with weight_col2:
            if valid_weight == 100:
                st.success(f"✓ {valid_weight}%")
            elif valid_weight > 100:
                st.error(f"⚠ {valid_weight}%")
            else:
                st.warning(f"{valid_weight}%")
        
        if st.session_state.job_description.strip():
            st.markdown("---")
            st.markdown("**Scoring Balance**")
            st.caption("How much weight to give job description vs. requirements?")
            
            st.session_state.jd_weight = st.slider(
                "Balance",
                min_value=0,
                max_value=100,
                value=st.session_state.jd_weight,
                label_visibility="collapsed"
            )
            
            balance_col1, balance_col2 = st.columns(2)
            with balance_col1:
                st.caption(f"Job Description: {st.session_state.jd_weight}%")
            with balance_col2:
                st.caption(f"Requirements: {100 - st.session_state.jd_weight}%")
        
        st.markdown("---")
        
        can_proceed = (valid_requirements and valid_weight == 100) or st.session_state.job_description.strip()
        
        if not can_proceed:
            st.info("Add weighted requirements (totaling 100%) or a job description to continue.")
        
        if st.button("🔍 Analyze Candidates", type="primary", use_container_width=True, disabled=not can_proceed):
            posting_id = st.session_state.selected_posting.get("id")
            
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
                            job_description=st.session_state.job_description if st.session_state.job_description.strip() else None,
                            weighted_requirements=valid_requirements,
                            jd_weight=st.session_state.jd_weight,
                            progress_callback=update_progress
                        )
                        
                        st.session_state.analysis_results = results
                        analysis_progress.empty()
                        analysis_status.empty()
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Analysis failed: {str(e)}")
                        analysis_progress.empty()
                        analysis_status.empty()

st.divider()
st.caption("Lever Analyzer - AI-powered candidate ranking and analysis")
