"""Streamlit user interface for the retail medallion pipeline."""

import json
import re
from pathlib import Path

from agents.provider import complete_json, extract_json
from agents.orchestrator import Orchestrator
from core.config import UPLOADS_DIR


def parse_suggestions(text: str) -> list[str]:
    """Parse three business-intent suggestions from wrapped JSON output."""
    values = extract_json(text, expected="array")
    return [str(value).strip() for value in values if str(value).strip()][:3]


def suggest_intents(columns: list[str]) -> list[str]:
    """Suggest three intents using the configured provider or offline mode."""
    result = complete_json(f"Suggest three retail analysis intents for columns {columns}", schema="array", columns=columns)
    return [str(item) for item in result[:3]]


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", Path(name).name)


def main() -> None:
    """Render the Streamlit application."""
    import pandas as pd
    import streamlit as st

    st.set_page_config(page_title="Retail Medallion Pipeline", layout="wide")
    st.title("Retail Medallion Pipeline")
    if "orchestrator" not in st.session_state:
        st.session_state.orchestrator = Orchestrator()
        st.session_state.state = None
    with st.sidebar:
        upload = st.file_uploader("Upload CSV", type=["csv"])
        intent = st.text_area("Business intent", "Understand revenue and fulfillment performance")
        upload_too_large = upload is not None and upload.size > 50 * 1024 * 1024
        if upload_too_large:
            st.error("The uploaded CSV exceeds the 50 MB limit.")
        if st.button("Analyze file", disabled=upload is None):
            try:
                st.session_state.suggestions = suggest_intents(list(pd.read_csv(upload).columns))
            except Exception as exc:
                st.error(f"Analyze File failed: {exc}. Check provider credentials or use offline mode.")
        for suggestion in st.session_state.get("suggestions", []):
            st.caption(suggestion)
        if st.button("Run pipeline", disabled=upload is None or upload_too_large):
            target = Path(UPLOADS_DIR) / _safe_name(upload.name)
            target.write_bytes(upload.getvalue())
            try:
                st.session_state.state = st.session_state.orchestrator.start_pipeline([str(target)], intent)
            except Exception as exc:
                st.error(f"Pipeline failed: {exc}")
        if st.button("Reset"):
            st.session_state.clear()
            st.rerun()
    state = st.session_state.get("state")
    if state is None:
        st.info("Upload a CSV to begin.")
        return
    labels = {"hitl_bronze": "Bronze review", "hitl_silver": "Silver review", "hitl_gold": "Gold review", "gold_data_ready": "Complete"}
    st.progress({"hitl_bronze": .25, "hitl_silver": .5, "hitl_gold": .75, "gold_data_ready": 1}.get(state.current_phase, 0))
    st.subheader(labels.get(state.current_phase, state.current_phase or "Pipeline"))
    layer = {"hitl_bronze": "bronze", "hitl_silver": "silver", "hitl_gold": "gold"}.get(state.current_phase)
    if layer:
        st.dataframe(st.session_state.orchestrator.get_sttm_for_review(state.identity, layer), use_container_width=True)
        feedback = st.text_area(f"{layer.title()} review feedback", key=f"feedback_{layer}")
        left, right = st.columns(2)
        if left.button(f"Approve {layer}"):
            st.session_state.state = st.session_state.orchestrator.approve_sttm(state.identity, layer)
            st.rerun()
        if right.button(f"Reject {layer}"):
            st.session_state.state = st.session_state.orchestrator.reject_sttm(state.identity, layer, feedback)
            st.rerun()
        if state.rejection_feedback.get(layer):
            st.write(state.rejection_feedback[layer])
    if state.current_phase == "gold_data_ready":
        if st.button("Generate report"):
            st.session_state.report = st.session_state.orchestrator.generate_report(state.identity)
        if st.session_state.get("report"):
            st.components.v1.html(Path(st.session_state.report).read_text(encoding="utf-8"), height=800, scrolling=True)


if __name__ == "__main__":
    main()