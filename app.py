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
from location_utils import filter_candidates_with_resumes_by_location, filter_candidates_by_location_fast
from export_utils import export_results_to_csv, filter_results_by_score

st.set_page_config(
    page_title="Lever Analyzer",
    page_icon="📊",
    layout="wide"
)

if "postings" not in st.session_state:
    st.session_state.postings = None
if "selected_postings" not in st.session_state:
    st.session_state.selected_postings = []
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
if "location_filter" not in st.session_state:
    st.session_state.location_filter = ""
if "location_filters" not in st.session_state:
    st.session_state.location_filters = []
if "country_filters" not in st.session_state:
    st.session_state.country_filters = []
if "minimum_score" not in st.session_state:
    st.session_state.minimum_score = 0
if "include_archived" not in st.session_state:
    st.session_state.include_archived = False

lever_api_key = os.environ.get("LEVER_API_KEY", "")
openai_api_key = os.environ.get("OPENAI_API_KEY", "")

missing_keys = []
if not lever_api_key:
    missing_keys.append("LEVER_API_KEY")
if not openai_api_key:
    missing_keys.append("OPENAI_API_KEY")

if missing_keys:
    st.error(f"Missing required API keys: {', '.join(missing_keys)}. Please add them to continue.")
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
    /* Hide location remove button by default, show on hover */
    .location-item {
        position: relative;
    }
    .location-item .stButton {
        opacity: 0;
        transition: opacity 0.2s;
    }
    .location-item:hover .stButton {
        opacity: 1;
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

# Sidebar for global filters
with st.sidebar:
    st.header("🌍 Filters")
    st.markdown("---")
    st.markdown("**Candidate Status**")
    st.session_state.include_archived = st.checkbox(
        "Include Archived Candidates",
        value=st.session_state.include_archived,
        help="When checked, analysis will include both active and archived candidates. When unchecked, only active (non-archived) candidates will be analyzed."
    )

    st.markdown("---")
    st.markdown("**Country Filter** (Optional)")
    st.caption("Filter by country (e.g., USA, UK, Canada). Press Enter after typing each country.")

    # Input box for adding new countries (using form to support Enter key)
    with st.form(key="country_form", clear_on_submit=True):
        new_country = st.text_input(
            "Add country",
            placeholder="Type country and press Enter",
            label_visibility="collapsed"
        )
        submitted_country = st.form_submit_button("➕ Add", use_container_width=True)

        if submitted_country and new_country and new_country.strip():
            country_to_add = new_country.strip()
            if country_to_add not in st.session_state.country_filters:
                st.session_state.country_filters.append(country_to_add)
                st.rerun()

    # Display existing country filters as a simple list
    if st.session_state.country_filters:
        st.markdown(f"**Countries ({len(st.session_state.country_filters)}):**")

        for idx, country in enumerate(st.session_state.country_filters):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.text(country)
            with col2:
                if st.button("✕", key=f"remove_country_{idx}", help=f"Remove {country}"):
                    st.session_state.country_filters.pop(idx)
                    st.rerun()
    else:
        st.caption("No countries added")

    st.markdown("---")
    st.markdown("**City/State/Region Filter** (Optional)")
    st.caption("Filter by city, state, or region (e.g., California, Bay Area, NYC Metro). Press Enter after typing each location.")

    # Input box for adding new locations (using form to support Enter key)
    with st.form(key="location_form", clear_on_submit=True):
        new_location = st.text_input(
            "Add location",
            placeholder="Type location and press Enter",
            label_visibility="collapsed"
        )
        submitted = st.form_submit_button("➕ Add", use_container_width=True)

        if submitted and new_location and new_location.strip():
            location_to_add = new_location.strip()
            if location_to_add not in st.session_state.location_filters:
                st.session_state.location_filters.append(location_to_add)
                st.rerun()

    # Display existing location filters as a simple list
    if st.session_state.location_filters:
        st.markdown(f"**Locations ({len(st.session_state.location_filters)}):**")

        for idx, location in enumerate(st.session_state.location_filters):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.text(location)
            with col2:
                if st.button("✕", key=f"remove_loc_{idx}", help=f"Remove {location}"):
                    st.session_state.location_filters.pop(idx)
                    st.rerun()
    else:
        st.caption("No locations added")

    # Minimum score filter (only show when results are available)
    if st.session_state.analysis_results:
        st.markdown("---")
        st.markdown("**Minimum Score**")
        st.caption("Filter results by minimum score threshold")
        st.session_state.minimum_score = st.slider(
            "Minimum Score",
            min_value=0,
            max_value=100,
            value=st.session_state.minimum_score,
            step=5,
            label_visibility="collapsed",
            help="Only show candidates with scores at or above this threshold"
        )

        if st.session_state.minimum_score > 0:
            st.info(f"Showing scores ≥ {st.session_state.minimum_score}")

if st.session_state.analysis_results:
    col_btn1, col_btn2, col_spacer = st.columns([1, 1, 2])

    with col_btn1:
        if st.button("🔄 Adjust & Re-run", type="primary", use_container_width=True):
            st.session_state.analysis_results = None
            st.session_state.current_step = 2
            st.session_state.minimum_score = 0
            st.rerun()

    with col_btn2:
        if st.button("← Start New Analysis", type="secondary", use_container_width=True):
            st.session_state.analysis_results = None
            st.session_state.current_step = 1
            st.session_state.selected_postings = []
            st.session_state.minimum_score = 0
            st.rerun()

    st.header("📈 Candidate Rankings")
    position_names = [p.get('text', 'Unknown') for p in st.session_state.selected_postings]
    st.caption(f"Positions: {', '.join(position_names)}")

    # Get all results
    all_results = st.session_state.analysis_results

    # Filter by minimum score
    results = filter_results_by_score(all_results, st.session_state.minimum_score)

    # Show filtering info and download button
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.session_state.minimum_score > 0:
            st.info(f"Showing {len(results)} of {len(all_results)} candidates (score ≥ {st.session_state.minimum_score})")
        else:
            st.info(f"Showing all {len(results)} candidates")

    with col2:
        # Download filtered results
        if results:
            csv_data = export_results_to_csv(results)
            st.download_button(
                label="📥 Download Filtered CSV",
                data=csv_data,
                file_name="candidate_analysis_filtered.csv",
                mime="text/csv",
                use_container_width=True
            )

    with col3:
        # Download all results
        if all_results:
            csv_data_all = export_results_to_csv(all_results)
            st.download_button(
                label="📥 Download All CSV",
                data=csv_data_all,
                file_name="candidate_analysis_all.csv",
                mime="text/csv",
                use_container_width=True
            )

    st.markdown("---")

    if not results:
        st.warning(f"No candidates found with score ≥ {st.session_state.minimum_score}. Try adjusting the minimum score filter.")
    else:
        # Find original rank from all_results
        for result in results:
            original_rank = all_results.index(result) + 1
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

            with st.expander(f"#{original_rank} {score_color} **{name}** - Score: {score}/100", expanded=(original_rank <= 3)):
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.markdown("**Summary:**")
                    st.write(analysis.get("summary", "No summary available"))

                    st.markdown("**Strengths:**")
                    strengths = analysis.get("strengths", [])
                    for strength in strengths:
                        # Handle both string and dict formats
                        if isinstance(strength, str):
                            st.markdown(f"✅ {strength}")
                        elif isinstance(strength, dict):
                            text = strength.get("text", strength.get("description", str(strength)))
                            st.markdown(f"✅ {text}")
                        else:
                            st.markdown(f"✅ {strength}")

                    st.markdown("**Weaknesses:**")
                    weaknesses = analysis.get("weaknesses", [])
                    for weakness in weaknesses:
                        # Handle both string and dict formats
                        if isinstance(weakness, str):
                            st.markdown(f"⚠️ {weakness}")
                        elif isinstance(weakness, dict):
                            text = weakness.get("text", weakness.get("description", str(weakness)))
                            st.markdown(f"⚠️ {text}")
                        else:
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
        st.markdown("### Step 1: Select Positions")
        st.caption("Choose one or more Lever positions to analyze candidates across multiple roles")
        
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

            # Preserve previously selected postings across reruns
            default_selections = [
                key for key, posting in posting_options.items()
                if posting.get('id') in [p.get('id') for p in st.session_state.selected_postings]
            ]

            selected_options = st.multiselect(
                "Search and select positions",
                options=list(posting_options.keys()),
                default=default_selections,
                help="Select one or more positions to analyze candidates across multiple roles",
                placeholder="Type to search and select positions..."
            )
            
            if selected_options:
                st.session_state.selected_postings = [posting_options[opt] for opt in selected_options]
                
                st.markdown("---")
                st.markdown(f"**Selected Positions ({len(selected_options)}):**")
                for posting in st.session_state.selected_postings:
                    st.write(f"• {posting.get('text', 'N/A')} ({posting.get('state', 'N/A')})")
                
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
        position_names = [p.get('text', 'Unknown') for p in st.session_state.selected_postings]
        if len(position_names) == 1:
            st.caption(f"Position: {position_names[0]}")
        else:
            st.caption(f"Positions: {len(position_names)} selected")
        
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
            all_candidates = []

            with st.spinner("Fetching candidates from Lever..."):
                for posting in st.session_state.selected_postings:
                    posting_id = posting.get("id")
                    try:
                        candidates = fetch_candidates_for_posting(posting_id, st.session_state.include_archived)
                        for c in candidates:
                            c["_posting_name"] = posting.get("text", "Unknown")
                        all_candidates.extend(candidates)
                    except Exception as e:
                        st.warning(f"Failed to fetch candidates for {posting.get('text', 'Unknown')}: {str(e)}")

            candidates = all_candidates

            # Show status of candidate fetching
            status_msg = f"Found {len(candidates)} candidate{'s' if len(candidates) != 1 else ''}"
            if st.session_state.include_archived:
                status_msg += " (including archived)"
            else:
                status_msg += " (active only)"
            st.info(status_msg)

            if not candidates:
                candidate_type = "candidates" if st.session_state.include_archived else "active candidates"
                st.warning(f"No {candidate_type} found for the selected positions.")
            else:
                # OPTIMIZATION: If location filters exist, do fast pre-filter before fetching resumes
                # This dramatically reduces resume fetching time
                candidates_to_fetch = candidates
                total_before_filter = len(candidates)
                candidates_matched_lever = []
                candidates_no_location = []

                if st.session_state.country_filters or st.session_state.location_filters:
                    # Build combined filter string
                    all_filters = []
                    if st.session_state.country_filters:
                        all_filters.extend(st.session_state.country_filters)
                    if st.session_state.location_filters:
                        all_filters.extend(st.session_state.location_filters)
                    combined_filter = '\n'.join(all_filters)

                    # Fast filter using only Lever location data (no resume needed)
                    st.info(f"Applying location pre-filter (using Lever data only)...")
                    candidates_matched_lever, candidates_no_location = filter_candidates_by_location_fast(
                        candidates,
                        combined_filter
                    )

                    candidates_to_fetch = candidates_matched_lever + candidates_no_location

                    filter_desc_parts = []
                    if st.session_state.country_filters:
                        filter_desc_parts.append(f"{', '.join(st.session_state.country_filters)}")
                    if st.session_state.location_filters:
                        filter_desc_parts.append(f"{', '.join(st.session_state.location_filters)}")

                    st.info(f"Pre-filter results: {len(candidates_matched_lever)} matched in Lever, {len(candidates_no_location)} need resume check. Fetching {len(candidates_to_fetch)} of {total_before_filter} resumes. Filters: {' | '.join(filter_desc_parts)}")

                # Fetch resumes for filtered candidates
                st.info(f"Fetching resumes for {len(candidates_to_fetch)} candidate{'s' if len(candidates_to_fetch) != 1 else ''}...")

                candidates_with_resumes = []
                progress_bar = st.progress(0)
                status_text = st.empty()

                for i, candidate in enumerate(candidates_to_fetch):
                    status_text.text(f"Fetching resume {i+1}/{len(candidates_to_fetch)}: {get_candidate_name(candidate)}")

                    resume_text = get_resume_text_for_candidate(candidate.get("id"))

                    if resume_text:
                        candidates_with_resumes.append({
                            "candidate": candidate,
                            "resume_text": resume_text
                        })

                    progress_bar.progress((i + 1) / len(candidates_to_fetch))

                progress_bar.empty()
                status_text.empty()

                if not candidates_with_resumes:
                    st.warning("No resumes found for any candidates.")
                else:
                    # If we had candidates with no Lever location, filter them now using resume data
                    if candidates_no_location and (st.session_state.country_filters or st.session_state.location_filters):
                        all_filters = []
                        if st.session_state.country_filters:
                            all_filters.extend(st.session_state.country_filters)
                        if st.session_state.location_filters:
                            all_filters.extend(st.session_state.location_filters)
                        combined_filter = '\n'.join(all_filters)

                        # Filter the ones that had no Lever location using resume data
                        candidates_no_lever_ids = {c.get("id") for c in candidates_no_location}
                        candidates_with_lever = [item for item in candidates_with_resumes if item["candidate"].get("id") not in candidates_no_lever_ids]
                        candidates_without_lever = [item for item in candidates_with_resumes if item["candidate"].get("id") in candidates_no_lever_ids]

                        # Filter the no-lever candidates using resume data
                        filtered_no_lever = filter_candidates_with_resumes_by_location(
                            candidates_without_lever,
                            combined_filter
                        )

                        # Combine: candidates matched by Lever + candidates matched by resume
                        candidates_with_resumes = candidates_with_lever + filtered_no_lever

                        st.info(f"Final count after resume-based filtering: {len(candidates_with_resumes)} candidates match your filters.")

                    if candidates_with_resumes:
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
                            analysis_progress.empty()
                            analysis_status.empty()
                            st.error(f"Error during analysis: {str(e)}")
                            raise

st.divider()
st.caption("Lever Analyzer - AI-powered candidate ranking and analysis")
