import json

from core.audit import AuditLogger
from core.memory import VectorMemory
from core.observability import AgentTrace
from core.state import PipelineState


def test_state_round_trip():
    state = PipelineState(identity="run", business_intent="sales", current_phase="bronze")
    assert PipelineState.from_dict(state.to_dict()).identity == "run"


def test_audit_and_trace(tmp_path):
    logger = AuditLogger("run", tmp_path)
    logger.log_event("agent", "phase", "event", {"ok": True})
    entry = json.loads((tmp_path / "audit_run.jsonl").read_text().strip())
    assert entry["event"] == "event"
    path = AgentTrace("agent", "run", tmp_path).save_trace({"ok": True})
    assert json.loads(open(path, encoding="utf-8").read())["status"] == "complete"


def test_memory_fallback(monkeypatch):
    memory = VectorMemory()
    memory.store_intent("sales performance", {"run_id": "run"})
    assert memory.retrieve_similar_intents("sales")[0]["metadata"]["run_id"] == "run"