import pandas as pd

from agents.orchestrator import Orchestrator
from streamlit_app import parse_suggestions, suggest_intents


def test_suggestion_parser_and_offline_suggestions():
    """Parse wrapped JSON and return deterministic offline suggestions."""
    assert parse_suggestions('Here are results: ["one", "two", "three"]') == ["one", "two", "three"]
    assert len(suggest_intents(["order_id", "amount"])) == 3


def test_offline_pipeline_hitl(tmp_path):
    """Advance a sample run through all three approval gates."""
    csv = tmp_path / "orders.csv"
    pd.DataFrame({
        "order_id": [1],
        "order_date": ["2024-01-01"],
        "customer_id": ["c1"],
        "quantity": [2],
        "unit_price": [5],
        "region": ["East"],
    }).to_csv(csv, index=False)
    orchestrator = Orchestrator()
    state = orchestrator.start_pipeline([str(csv)], "revenue", "integration")
    assert state.current_phase == "hitl_bronze"
    state = orchestrator.approve_sttm("integration", "bronze")
    state = orchestrator.approve_sttm("integration", "silver")
    state = orchestrator.approve_sttm("integration", "gold")
    assert state.current_phase == "gold_data_ready"
