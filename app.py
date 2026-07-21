from __future__ import annotations

import json

import streamlit as st

from src.anthropic_client import ResearchError
from src.cache import ReportCache
from src.config import PROFILES, load_settings
from src.export import export_report
from src.report_service import ReportResult, generate_report

settings = load_settings()
st.set_page_config(
    page_title="Competitive Intelligence Copilot",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
<style>
.block-container {max-width: 1180px; padding-top: 2rem;}
[data-testid="stMetricValue"] {font-size: 1.35rem;}
.small-note {color: #5b6673; font-size: 0.86rem;}
</style>
""",
    unsafe_allow_html=True,
)

st.title("Competitive Intelligence Copilot")
st.caption(
    "Research a company, compare three strategically relevant competitors, "
    "and generate a source-backed executive report."
)

with st.sidebar:
    st.header("Research settings")
    if settings.api_key_configured:
        st.success("Anthropic API key detected")
    else:
        st.error("Anthropic API key not configured")
        st.markdown(
            "Add `ANTHROPIC_API_KEY` as a Codespaces secret or copy "
            "`.env.example` to `.env`."
        )

    mode_keys = list(PROFILES)
    default_index = mode_keys.index(settings.default_mode)
    mode = st.radio(
        "Research depth",
        options=mode_keys,
        index=default_index,
        format_func=lambda key: PROFILES[key].label,
    )
    selected_profile = PROFILES[mode]
    st.caption(selected_profile.description)

    force_refresh = st.checkbox(
        "Force fresh research",
        help="Ignore a recent report and generate a new analysis.",
    )

    with st.expander("Advanced"):
        if st.button("Clear recent reports"):
            removed = ReportCache(
                settings.cache_dir,
                settings.prompt_version,
            ).clear()
            st.success(f"Removed {removed} cached report(s).")

company_name = st.text_input(
    "Company to assess",
    placeholder="Example: Workday",
    disabled=not settings.api_key_configured,
)

run_clicked = st.button(
    "Generate report",
    type="primary",
    disabled=not settings.api_key_configured or not company_name.strip(),
)

if run_clicked:
    progress_placeholder = st.empty()

    def update_progress(message: str) -> None:
        progress_placeholder.info(message)

    try:
        with st.spinner("Building competitive intelligence..."):
            result = generate_report(
                company_name=company_name,
                mode=mode,
                settings=settings,
                force_refresh=force_refresh,
                progress=update_progress,
            )
            paths = export_report(result.report, settings.output_dir)
        progress_placeholder.empty()
        st.session_state["report_result"] = result
        st.session_state["report_json"] = paths.json_path.read_bytes()
        st.session_state["report_pdf"] = paths.pdf_path.read_bytes()
        st.session_state["json_name"] = paths.json_path.name
        st.session_state["pdf_name"] = paths.pdf_path.name
    except (ResearchError, ValueError) as exc:
        progress_placeholder.empty()
        st.error(str(exc))
    except Exception as exc:  # pragma: no cover - UI safety net
        progress_placeholder.empty()
        st.exception(exc)

result = st.session_state.get("report_result")
if isinstance(result, ReportResult):
    report = result.report
    if result.cache_hit:
        st.success("Loaded a recent report.")
    else:
        st.success("Report generated successfully.")

    metric_columns = st.columns(3)
    metric_columns[0].metric("Research depth", result.profile.label)
    metric_columns[1].metric("Competitors", len(report.competitors))
    metric_columns[2].metric("Sources", report.source_count)

    download_col1, download_col2, _ = st.columns([1, 1, 3])
    download_col1.download_button(
        "Download PDF",
        data=st.session_state["report_pdf"],
        file_name=st.session_state["pdf_name"],
        mime="application/pdf",
        width="stretch",
    )
    download_col2.download_button(
        "Download JSON",
        data=st.session_state["report_json"],
        file_name=st.session_state["json_name"],
        mime="application/json",
        width="stretch",
    )

    summary_tab, competitors_tab, strategy_tab, sources_tab = st.tabs(
        ["Summary", "Competitors", "Strategy", "Sources"]
    )

    with summary_tab:
        st.subheader("Executive summary")
        st.write(report.executive_summary)
        st.subheader("Market definition")
        st.write(report.market_definition)
        st.caption(report.methodology_and_limitations)

    with competitors_tab:
        for competitor in report.competitors:
            with st.expander(
                f"#{competitor.rank} {competitor.name} · "
                f"{competitor.overlap_score}/100 overlap",
                expanded=competitor.rank == 1,
            ):
                st.write(competitor.why_it_matters)
                st.markdown(f"**Positioning:** {competitor.positioning}")
                left, right = st.columns(2)
                with left:
                    st.markdown("**Differentiators**")
                    for item in competitor.key_differentiators:
                        st.markdown(f"- {item}")
                    st.markdown("**Threats**")
                    for item in competitor.threats:
                        st.markdown(f"- {item}")
                with right:
                    st.markdown("**Strategic signals**")
                    signals = (
                        competitor.recent_product_signals
                        + competitor.leadership_and_hiring_signals
                        + competitor.ecosystem_and_gtm_signals
                    )
                    for signal in signals:
                        implication = (
                            f" — {signal.strategic_implication}"
                            if signal.strategic_implication
                            else ""
                        )
                        st.markdown(
                            f"- **{signal.title}**: {signal.summary}{implication}"
                        )
                    st.markdown("**Opportunities**")
                    for item in competitor.opportunities:
                        st.markdown(f"- {item}")

    with strategy_tab:
        sections = [
            ("Cross-competitor themes", report.cross_competitor_themes),
            ("Whitespace opportunities", report.whitespace_opportunities),
            ("Strategic threats", report.strategic_threats),
            ("Recommended actions", report.recommended_actions),
            ("Watchlist", report.watchlist),
        ]
        for heading, items in sections:
            st.subheader(heading)
            for item in items:
                st.markdown(f"- {item}")

    with sources_tab:
        source_rows = []
        for competitor in report.competitors:
            for evidence in competitor.evidence:
                source_rows.append(
                    {
                        "Competitor": competitor.name,
                        "Claim": evidence.claim,
                        "Source": evidence.source_title,
                        "Date": evidence.published_date,
                        "Confidence": evidence.confidence.value,
                        "URL": evidence.source_url,
                    }
                )
        st.dataframe(source_rows, width="stretch", hide_index=True)
        with st.expander("Raw report JSON"):
            st.json(json.loads(st.session_state["report_json"]))
