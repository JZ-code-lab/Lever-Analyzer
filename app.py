import streamlit as st
import os
from lever_client import (
    fetch_all_postings,
    fetch_candidates_for_posting,
    fetch_all_stages,
    fetch_archive_reasons,
    change_candidate_stage,
    archive_candidate,
    get_resume_text_for_candidate,
    get_candidate_name,
    get_candidate_email,
    get_candidate_linkedin,
    get_candidate_lever_url
)
from resume_analyzer import analyze_candidates_batch
from location_utils import filter_candidates_with_resumes_by_location, filter_candidates_by_location_fast
from export_utils import export_results_to_csv, filter_results_by_score

# Stage filter options — first item is the special "archive" status flag,
# the rest are active Lever stages (matched case-insensitively).
STAGE_FILTER_OPTIONS = [
    "archive",
    "new applicant",
    "new lead",
    "reached out",
    "pass resume screen",
    "HR phone screen",
    "tech screen 1",
    "tech screen 2",
    "onsite",
    "coding test",
]


def default_stage_filters() -> dict:
    return {s: False for s in STAGE_FILTER_OPTIONS}


def default_disqualifiers() -> list:
    return [{"text": ""}, {"text": ""}]

st.set_page_config(
    page_title="Lever Analyzer",
    page_icon="📊",
    layout="wide"
)

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { min-width: 240px !important; max-width: 240px !important; }
    [data-testid="stSidebar"] > div:first-child { width: 240px !important; }
    </style>
    """,
    unsafe_allow_html=True,
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
if "stage_filters" not in st.session_state:
    st.session_state.stage_filters = default_stage_filters()
if "disqualifiers" not in st.session_state:
    st.session_state.disqualifiers = default_disqualifiers()
if "lever_stages_cache" not in st.session_state:
    st.session_state.lever_stages_cache = None
if "archive_reasons_cache" not in st.session_state:
    st.session_state.archive_reasons_cache = None
if "recent_stage_changes" not in st.session_state:
    # Maps opportunity_id -> human-readable note like "Moved to onsite" or "Archived: Not qualified"
    st.session_state.recent_stage_changes = {}
if "require_hands_on_coding" not in st.session_state:
    st.session_state.require_hands_on_coding = False

lever_api_key = os.environ.get("LEVER_API_KEY", "")
openai_api_key = os.environ.get("OPENAI_API_KEY", "")
lever_perform_as_user_id = os.environ.get("LEVER_PERFORM_AS_USER_ID", "")
github_api_token = os.environ.get("GITHUB_API_TOKEN", "")

missing_keys = []
if not lever_api_key:
    missing_keys.append("LEVER_API_KEY")
if not openai_api_key:
    missing_keys.append("OPENAI_API_KEY")

if missing_keys:
    st.error(f"Missing required API keys: {', '.join(missing_keys)}. Please add them to continue.")
    st.stop()

# Optional: Show info if GitHub token not set and hands-on coding filter is enabled
if not github_api_token and st.session_state.get("require_hands_on_coding", False):
    st.info("💡 Optional: Set GITHUB_API_TOKEN environment variable for higher GitHub API rate limits (5000/hr vs 60/hr)")

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
    # Start New Search button - accessible from any page
    if st.button("🔄 Start New Search", type="primary", use_container_width=True):
        # Reset all session state to start fresh
        st.session_state.analysis_results = None
        st.session_state.current_step = 1
        st.session_state.selected_postings = []
        st.session_state.minimum_score = 0
        st.session_state.job_description = ""
        st.session_state.requirements = [
            {"requirement": "", "weight": 25},
            {"requirement": "", "weight": 25},
            {"requirement": "", "weight": 25},
            {"requirement": "", "weight": 25}
        ]
        st.session_state.jd_weight = 50
        st.session_state.country_filters = []
        st.session_state.location_filters = []
        st.session_state.stage_filters = default_stage_filters()
        st.session_state.disqualifiers = default_disqualifiers()
        st.session_state.require_hands_on_coding = False
        st.rerun()

    st.markdown("---")
    st.header("🌍 Filters")
    st.markdown("---")
    st.markdown("**Include candidates in the following stages:**")
    for stage_name in STAGE_FILTER_OPTIONS:
        st.session_state.stage_filters[stage_name] = st.checkbox(
            stage_name,
            value=st.session_state.stage_filters.get(stage_name, False),
            key=f"stage_filter_{stage_name}"
        )

    st.markdown("")
    st.session_state.require_hands_on_coding = st.checkbox(
        "Strong indication of recent hands-on coding skills",
        value=st.session_state.require_hands_on_coding,
        help="When checked, analyzes candidates for GitHub activity, technical content creation (articles, videos, podcasts, talks), and hands-on coding evidence. Uses job requirements to determine relevance."
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
            # Reset all session state to start fresh
            st.session_state.analysis_results = None
            st.session_state.current_step = 1
            st.session_state.selected_postings = []
            st.session_state.minimum_score = 0
            st.session_state.job_description = ""
            st.session_state.requirements = [
                {"requirement": "", "weight": 25},
                {"requirement": "", "weight": 25},
                {"requirement": "", "weight": 25},
                {"requirement": "", "weight": 25}
            ]
            st.session_state.jd_weight = 50
            st.session_state.country_filters = []
            st.session_state.location_filters = []
            st.session_state.stage_filters = default_stage_filters()
            st.session_state.disqualifiers = default_disqualifiers()
            st.session_state.require_hands_on_coding = False
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

    # ----- Bulk archive panel -----
    disqualified_results = [r for r in all_results if r.get("analysis", {}).get("has_disqualifier")]
    not_yet_archived_disq = [r for r in disqualified_results if not r.get("candidate", {}).get("archived")]

    with st.expander(f"⚡ Bulk Archive ({len(not_yet_archived_disq)} disqualified, not yet archived)", expanded=False):
        if not lever_perform_as_user_id:
            st.warning("Set LEVER_PERFORM_AS_USER_ID on Render to enable bulk archive.")
        else:
            bulk_criterion = st.radio(
                "Select candidates to archive:",
                options=["Disqualified candidates", "Candidates with score below threshold"],
                key="bulk_criterion",
                horizontal=True,
            )

            if bulk_criterion == "Disqualified candidates":
                targets = not_yet_archived_disq
                st.caption(f"{len(targets)} candidate{'s' if len(targets) != 1 else ''} marked as disqualified and not yet archived.")
            else:
                threshold = st.slider(
                    "Archive candidates with score strictly less than:",
                    min_value=0, max_value=100, value=30, step=5,
                    key="bulk_score_threshold",
                )
                targets = [
                    r for r in all_results
                    if not r.get("candidate", {}).get("archived")
                    and r.get("analysis", {}).get("overall_score", 0) < threshold
                ]
                st.caption(f"{len(targets)} candidate{'s' if len(targets) != 1 else ''} with score < {threshold} and not yet archived.")

            # Reason picker (lazy-load reasons)
            if st.session_state.archive_reasons_cache is None:
                try:
                    st.session_state.archive_reasons_cache = fetch_archive_reasons()
                except Exception as fetch_err:
                    st.error(f"Could not load archive reasons: {fetch_err}")
                    st.session_state.archive_reasons_cache = []

            reasons = st.session_state.archive_reasons_cache or []
            if not reasons:
                st.warning("No archive reasons available in this Lever account.")
            else:
                reason_labels = [r.get("text", "") for r in reasons]
                bulk_reason_label = st.selectbox(
                    "Archive reason for all selected:",
                    options=reason_labels,
                    key="bulk_archive_reason",
                )
                bulk_reason_id = next(
                    (r.get("id") for r in reasons if r.get("text") == bulk_reason_label),
                    None,
                )

                # Two-step confirmation: first click arms, second click fires
                arm_key = "bulk_archive_armed"
                if arm_key not in st.session_state:
                    st.session_state[arm_key] = False

                if not targets:
                    st.info("No candidates match the criteria above.")
                elif not st.session_state[arm_key]:
                    if st.button(f"Archive {len(targets)} candidate{'s' if len(targets) != 1 else ''}", type="primary", key="bulk_archive_arm"):
                        st.session_state[arm_key] = True
                        st.rerun()
                else:
                    st.warning(f"About to archive {len(targets)} candidate{'s' if len(targets) != 1 else ''} with reason: **{bulk_reason_label}**. This calls Lever's API for each candidate.")
                    col_confirm, col_cancel = st.columns(2)
                    with col_confirm:
                        confirm = st.button(f"✅ Confirm archive {len(targets)}", type="primary", key="bulk_archive_confirm")
                    with col_cancel:
                        cancel = st.button("Cancel", key="bulk_archive_cancel")

                    if cancel:
                        st.session_state[arm_key] = False
                        st.rerun()

                    if confirm and bulk_reason_id:
                        progress = st.progress(0)
                        status = st.empty()
                        succeeded = 0
                        failed = []
                        for i, r in enumerate(targets):
                            cid = r.get("candidate", {}).get("id", "")
                            cname = get_candidate_name(r.get("candidate", {}))
                            status.text(f"Archiving {i + 1}/{len(targets)}: {cname}")
                            try:
                                archive_candidate(cid, bulk_reason_id, lever_perform_as_user_id)
                                # Update local state so UI reflects archive without re-fetching
                                r["candidate"]["archived"] = {"reason": bulk_reason_id}
                                st.session_state.recent_stage_changes[cid] = f"Archived: {bulk_reason_label}"
                                succeeded += 1
                            except Exception as bulk_err:
                                failed.append((cname, str(bulk_err)))
                            progress.progress((i + 1) / len(targets))

                        progress.empty()
                        status.empty()
                        st.session_state[arm_key] = False

                        if failed:
                            st.error(f"Archived {succeeded}/{len(targets)}. {len(failed)} failed:")
                            for fname, ferr in failed[:10]:
                                st.caption(f"• {fname}: {ferr}")
                            if len(failed) > 10:
                                st.caption(f"...and {len(failed) - 10} more.")
                        else:
                            st.success(f"✅ Archived all {succeeded} candidate{'s' if succeeded != 1 else ''}.")

    if not results:
        st.warning(f"No candidates found with score ≥ {st.session_state.minimum_score}. Try adjusting the minimum score filter.")
    else:
        # Find original rank from all_results
        for result in results:
            original_rank = all_results.index(result) + 1
            candidate = result["candidate"]
            analysis = result["analysis"]

            score = analysis.get("overall_score", 0)
            is_disqualified = bool(analysis.get("has_disqualifier"))
            disqualifier_reason = analysis.get("disqualifier_reason", "")

            if is_disqualified:
                score_color = "⛔"
            elif score >= 80:
                score_color = "🟢"
            elif score >= 60:
                score_color = "🟡"
            else:
                score_color = "🔴"

            name = get_candidate_name(candidate)
            email = get_candidate_email(candidate)
            linkedin = get_candidate_linkedin(candidate)
            lever_url = get_candidate_lever_url(candidate)

            header_suffix = " — DISQUALIFIED" if is_disqualified else ""
            with st.expander(f"#{original_rank} {score_color} **{name}** - Score: {score}/100{header_suffix}", expanded=(original_rank <= 3)):
                col1, col2 = st.columns([3, 2])

                with col1:
                    st.markdown("**Resume:**")
                    resume_text = result.get("resume_text", "")
                    with st.container(height=600, border=True):
                        if resume_text:
                            st.text(resume_text)
                        else:
                            st.caption("No resume text available for this candidate.")

                with col2:
                    st.metric("Overall Score", f"{score}/100")

                    if is_disqualified:
                        st.error(f"⛔ **Disqualified:** {disqualifier_reason or 'Matched a disqualifier.'}")

                    if analysis.get("jd_match_score") is not None:
                        st.write(f"JD Match: {analysis.get('jd_match_score')}/100")

                    st.markdown("**Summary:**")
                    st.write(analysis.get("summary", "No summary available"))

                    technical_analysis = analysis.get("technical_indicators_analysis")
                    if technical_analysis:
                        st.markdown("**Technical Indicators:**")
                        st.info(technical_analysis)

                    st.markdown("**Strengths:**")
                    strengths = analysis.get("strengths", [])
                    for strength in strengths:
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
                        if isinstance(weakness, str):
                            st.markdown(f"⚠️ {weakness}")
                        elif isinstance(weakness, dict):
                            text = weakness.get("text", weakness.get("description", str(weakness)))
                            st.markdown(f"⚠️ {text}")
                        else:
                            st.markdown(f"⚠️ {weakness}")

                    st.divider()

                    st.markdown("**Links:**")
                    st.markdown(f"[📋 Lever Profile]({lever_url})")

                    if linkedin:
                        st.markdown(f"[💼 LinkedIn]({linkedin})")

                    if email:
                        st.write(f"📧 {email}")

                    # ----- Change Stage -----
                    st.divider()
                    st.markdown("**Change Stage in Lever:**")

                    opportunity_id = candidate.get("id", "")
                    stages_cache = st.session_state.get("lever_stages_cache") or []
                    stage_id_to_name = {s.get("id"): s.get("text", "") for s in stages_cache}

                    # Current stage label (or "archived")
                    if candidate.get("archived"):
                        current_stage_label = "(archived)"
                    else:
                        stage_value = candidate.get("stage")
                        if isinstance(stage_value, dict):
                            current_stage_label = stage_value.get("text", "(unknown)")
                        else:
                            current_stage_label = stage_id_to_name.get(stage_value, "(unknown)")
                    st.caption(f"Currently: {current_stage_label}")

                    # Recent-change indicator (persists across reruns)
                    recent_change = st.session_state.recent_stage_changes.get(opportunity_id)
                    if recent_change:
                        st.success(f"✓ {recent_change}")

                    # Move-to dropdown — put "archive" last so it's harder to misclick
                    stage_move_options = [s for s in STAGE_FILTER_OPTIONS if s != "archive"] + ["archive"]
                    selected_target = st.selectbox(
                        "Move to",
                        options=["(no change)"] + stage_move_options,
                        index=0,
                        key=f"stage_target_{opportunity_id}",
                        label_visibility="collapsed",
                    )

                    selected_reason_id = None
                    selected_reason_label = ""
                    if selected_target == "archive":
                        # Lazy-load archive reasons on first use
                        if st.session_state.archive_reasons_cache is None:
                            try:
                                st.session_state.archive_reasons_cache = fetch_archive_reasons()
                            except Exception as fetch_err:
                                st.error(f"Could not load archive reasons: {fetch_err}")
                                st.session_state.archive_reasons_cache = []
                        reasons = st.session_state.archive_reasons_cache or []
                        if reasons:
                            reason_labels = [r.get("text", "") for r in reasons]
                            selected_reason_label = st.selectbox(
                                "Archive reason",
                                options=reason_labels,
                                key=f"archive_reason_{opportunity_id}",
                            )
                            selected_reason_id = next(
                                (r.get("id") for r in reasons if r.get("text") == selected_reason_label),
                                None,
                            )
                        else:
                            st.warning("No archive reasons available in this Lever account.")

                    # Apply button — only shown once a real target is selected
                    if selected_target != "(no change)":
                        apply_disabled = (
                            not lever_perform_as_user_id
                            or (selected_target == "archive" and not selected_reason_id)
                        )
                        if not lever_perform_as_user_id:
                            st.caption("⚠️ Set LEVER_PERFORM_AS_USER_ID on Render to enable stage changes.")
                        if st.button("Apply", key=f"apply_stage_{opportunity_id}", disabled=apply_disabled, type="primary"):
                            try:
                                if selected_target == "archive":
                                    archive_candidate(opportunity_id, selected_reason_id, lever_perform_as_user_id)
                                    candidate["archived"] = {"reason": selected_reason_id}
                                    st.session_state.recent_stage_changes[opportunity_id] = f"Archived: {selected_reason_label}"
                                else:
                                    # Resolve UI stage name -> Lever stage ID (case-insensitive match)
                                    target_lower = selected_target.strip().lower()
                                    target_stage_id = next(
                                        (s.get("id") for s in stages_cache
                                         if s.get("text", "").strip().lower() == target_lower),
                                        None,
                                    )
                                    if not target_stage_id:
                                        st.error(f"Could not find a Lever stage matching '{selected_target}'.")
                                    else:
                                        change_candidate_stage(opportunity_id, target_stage_id, lever_perform_as_user_id)
                                        candidate["stage"] = target_stage_id
                                        candidate["archived"] = None
                                        st.session_state.recent_stage_changes[opportunity_id] = f"Moved to {selected_target}"
                                st.rerun()
                            except Exception as apply_err:
                                st.error(f"Update failed: {apply_err}")

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

        # Disqualifiers (optional)
        st.markdown("---")
        st.markdown("**Disqualifiers** (Optional)")
        st.caption("If a candidate has any of these, they automatically score 0/100.")

        disqualifiers_to_remove = []
        for i, dq in enumerate(st.session_state.disqualifiers):
            dq_col1, dq_col2 = st.columns([5, 0.5])
            with dq_col1:
                st.session_state.disqualifiers[i]["text"] = st.text_input(
                    f"Disqualifier {i+1}",
                    value=dq["text"],
                    key=f"disqualifier_{i}",
                    label_visibility="collapsed",
                    placeholder="e.g., No bachelor's degree"
                )
            with dq_col2:
                if len(st.session_state.disqualifiers) > 1:
                    if st.button("✕", key=f"remove_disqualifier_{i}"):
                        disqualifiers_to_remove.append(i)

        for i in reversed(disqualifiers_to_remove):
            st.session_state.disqualifiers.pop(i)
            st.rerun()

        if st.button("+ Add Disqualifier"):
            st.session_state.disqualifiers.append({"text": ""})
            st.rerun()

        active_disqualifiers = [d["text"].strip() for d in st.session_state.disqualifiers if d["text"].strip()]
        
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
            stage_filters = st.session_state.stage_filters
            include_archived = stage_filters.get("archive", False)
            active_stage_names = [s for s in STAGE_FILTER_OPTIONS if s != "archive" and stage_filters.get(s, False)]
            include_active = bool(active_stage_names)

            if not include_active and not include_archived:
                st.warning("Select at least one stage in the sidebar before analyzing.")
                st.stop()

            # Build a stage_id -> stage_name map once (cached for the session)
            try:
                if st.session_state.lever_stages_cache is None:
                    st.session_state.lever_stages_cache = fetch_all_stages()
                stage_id_to_name = {
                    s.get("id"): s.get("text", "")
                    for s in (st.session_state.lever_stages_cache or [])
                }
            except Exception as e:
                st.warning(f"Could not fetch Lever stages: {e}. Stage filtering may be inaccurate.")
                stage_id_to_name = {}

            active_stage_names_lower = {s.strip().lower() for s in active_stage_names}

            all_candidates = []

            with st.spinner("Fetching candidates from Lever..."):
                for posting in st.session_state.selected_postings:
                    posting_id = posting.get("id")
                    try:
                        candidates = fetch_candidates_for_posting(
                            posting_id,
                            include_active=include_active,
                            include_archived=include_archived,
                        )
                        for c in candidates:
                            c["_posting_name"] = posting.get("text", "Unknown")
                        all_candidates.extend(candidates)
                    except Exception as e:
                        st.warning(f"Failed to fetch candidates for {posting.get('text', 'Unknown')}: {str(e)}")

            # Deduplicate candidates based on lever profile link and email
            seen_candidates = {}
            for candidate in all_candidates:
                lever_url = get_candidate_lever_url(candidate)
                email = get_candidate_email(candidate)

                # Create unique key from lever URL (primary) and email (secondary)
                unique_key = (lever_url, email)

                if unique_key not in seen_candidates:
                    seen_candidates[unique_key] = candidate

            candidates = list(seen_candidates.values())

            # Filter by stage: archived candidates kept iff "archive" is checked;
            # active candidates kept iff their stage matches one of the checked stages.
            stage_filtered = []
            for c in candidates:
                if c.get("archived"):
                    if include_archived:
                        stage_filtered.append(c)
                    continue
                stage_value = c.get("stage")
                if isinstance(stage_value, dict):
                    stage_name = stage_value.get("text", "")
                else:
                    stage_name = stage_id_to_name.get(stage_value, "")
                if stage_name.strip().lower() in active_stage_names_lower:
                    stage_filtered.append(c)

            candidates = stage_filtered

            # Show deduplication results if duplicates were found
            duplicates_removed = len(all_candidates) - len(candidates)
            if duplicates_removed > 0:
                st.info(f"Removed {duplicates_removed} duplicate or out-of-stage candidate{'s' if duplicates_removed != 1 else ''}")

            # Show status of candidate fetching
            selected_stages_summary = ", ".join([s for s in STAGE_FILTER_OPTIONS if stage_filters.get(s, False)])
            st.info(f"Found {len(candidates)} candidate{'s' if len(candidates) != 1 else ''} in stages: {selected_stages_summary}")

            if not candidates:
                st.warning("No candidates found in the selected stages for the chosen positions.")
            else:
                # OPTIMIZATION: If location filters exist, do fast pre-filter before fetching resumes
                # This dramatically reduces resume fetching time by filtering out candidates from
                # different countries/states using only Lever data (no resume fetch needed)
                candidates_to_fetch = candidates
                total_before_filter = len(candidates)
                candidates_matched_lever = []
                candidates_need_resume_check = []

                if st.session_state.country_filters or st.session_state.location_filters:
                    # Apply filters sequentially (AND logic): country first, then location
                    # This ensures "United States" + "Bay Area" means "Bay Area in the United States"
                    st.info(f"Applying location pre-filter (using Lever data only)...")

                    current_candidates = candidates

                    # Step 1: Apply country filters (if any) with OR logic among countries
                    if st.session_state.country_filters:
                        country_filter = '\n'.join(st.session_state.country_filters)
                        country_matched, country_needs_check = filter_candidates_by_location_fast(
                            current_candidates,
                            country_filter
                        )
                        current_candidates = country_matched + country_needs_check
                        st.info(f"After country filter: {len(current_candidates)} candidates in {', '.join(st.session_state.country_filters)}")

                    # Step 2: Apply location filters (if any) with OR logic among locations
                    # on the country-filtered results
                    if st.session_state.location_filters:
                        location_filter = '\n'.join(st.session_state.location_filters)

                        # Show progress for location filtering (can be slow for large regions like Bay Area)
                        location_status = st.empty()
                        location_status.info(f"Filtering by location: {', '.join(st.session_state.location_filters)}... (this may take a moment)")

                        candidates_matched_lever, candidates_need_resume_check = filter_candidates_by_location_fast(
                            current_candidates,
                            location_filter
                        )

                        location_status.empty()
                        st.info(f"After location filter: {len(candidates_matched_lever)} exact matches, {len(candidates_need_resume_check)} need resume check")
                    else:
                        # No location filter, so all country-filtered candidates need resume check
                        # (unless they exactly matched the country)
                        candidates_matched_lever, candidates_need_resume_check = filter_candidates_by_location_fast(
                            current_candidates,
                            country_filter if st.session_state.country_filters else ""
                        )

                    candidates_to_fetch = candidates_matched_lever + candidates_need_resume_check

                    filter_desc = []
                    if st.session_state.country_filters:
                        filter_desc.append(f"Country: {', '.join(st.session_state.country_filters)}")
                    if st.session_state.location_filters:
                        filter_desc.append(f"Location: {', '.join(st.session_state.location_filters)}")

                    st.info(f"Pre-filter complete: Fetching {len(candidates_to_fetch)} of {total_before_filter} resumes. Filters: {' | '.join(filter_desc)}")

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
                    # Filter candidates that need resume check (no/vague Lever location or same region)
                    # These candidates use multi-source detection: resume text, phone area codes
                    if candidates_need_resume_check and (st.session_state.country_filters or st.session_state.location_filters):
                        # Separate candidates: those matched in Lever vs those needing resume-based filtering
                        candidates_need_check_ids = {c.get("id") for c in candidates_need_resume_check}
                        candidates_matched_lever_with_resume = [item for item in candidates_with_resumes if item["candidate"].get("id") not in candidates_need_check_ids]
                        candidates_to_check_with_resume = [item for item in candidates_with_resumes if item["candidate"].get("id") in candidates_need_check_ids]

                        # Apply filters sequentially (AND logic) on resume data
                        filtered_by_resume = candidates_to_check_with_resume

                        # Step 1: Apply country filter (if any)
                        if st.session_state.country_filters:
                            country_filter = '\n'.join(st.session_state.country_filters)
                            filtered_by_resume = filter_candidates_with_resumes_by_location(
                                filtered_by_resume,
                                country_filter
                            )

                        # Step 2: Apply location filter (if any) on country-filtered results
                        if st.session_state.location_filters:
                            location_filter = '\n'.join(st.session_state.location_filters)
                            filtered_by_resume = filter_candidates_with_resumes_by_location(
                                filtered_by_resume,
                                location_filter
                            )

                        # Combine: candidates matched by Lever + candidates matched by resume/phone
                        candidates_with_resumes = candidates_matched_lever_with_resume + filtered_by_resume

                        st.info(f"Final count after multi-source filtering: {len(candidates_with_resumes)} candidates match your filters ({len(candidates_matched_lever_with_resume)} from Lever, {len(filtered_by_resume)} from resume/phone).")

                    if candidates_with_resumes:
                        candidates_before_analysis = len(candidates_with_resumes)

                        # Show info about hands-on coding filter if enabled
                        if st.session_state.require_hands_on_coding:
                            st.info(f"🔍 Checking {candidates_before_analysis} candidates for hands-on coding indicators (GitHub, technical content)...")
                        else:
                            st.info(f"Analyzing {candidates_before_analysis} candidates with resumes...")

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
                                require_hands_on_coding=st.session_state.require_hands_on_coding,
                                progress_callback=update_progress,
                                disqualifiers=active_disqualifiers
                            )

                            # Show filtering results if hands-on coding filter was enabled
                            if st.session_state.require_hands_on_coding:
                                candidates_after_filter = len(results)
                                filtered_out = candidates_before_analysis - candidates_after_filter
                                if filtered_out > 0:
                                    st.warning(f"⚠️ Filtered out {filtered_out} candidate{'s' if filtered_out != 1 else ''} without strong hands-on coding indicators. {candidates_after_filter} candidate{'s' if candidates_after_filter != 1 else ''} met the requirement.")
                                else:
                                    st.success(f"✅ All {candidates_after_filter} candidate{'s' if candidates_after_filter != 1 else ''} have strong hands-on coding indicators.")

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
