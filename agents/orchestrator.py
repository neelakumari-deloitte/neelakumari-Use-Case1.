"""LangGraph-compatible pipeline orchestration with HITL gates."""

from pathlib import Path
from uuid import uuid4

from agents.bronze_agent import run_bronze_agent
from agents.gold_agent import run_gold_agent
from agents.profiler import run_profiler
from agents.reporter import run_reporter
from agents.silver_agent import run_silver_agent
from agents.sttm_generator import run_sttm_generator
from core.state import PipelineState

try:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command, interrupt
except ImportError:  # pragma: no cover
    MemorySaver = None
    StateGraph = None
    START = END = None
    Command = interrupt = None


class Orchestrator:
    """Coordinate pipeline phases and human approval gates."""

    def __init__(self) -> None:
        self.states: dict[str, PipelineState] = {}
        self.graph = self._build_graph()

    def _build_graph(self):
        """Build the executable LangGraph phase graph when LangGraph is available."""
        if StateGraph is None:
            return None

        def phase_1(state: dict) -> dict:
            run_id = state["identity"]
            profile = run_profiler(state["input_paths"][0], state.get("business_intent", ""), run_id)
            feedback = "\n".join(state.get("rejection_feedback", {}).get("bronze", []))
            sttm = run_sttm_generator(profile, "bronze", state.get("business_intent", ""), run_id, reviewer_feedback=feedback)
            return {"phase_outputs": {**state.get("phase_outputs", {}), "profile": profile, "bronze_sttm": sttm}, "current_phase": "hitl_bronze"}

        def phase_2(state: dict) -> dict:
            run_id = state["identity"]
            outputs = state["phase_outputs"]
            bronze = run_bronze_agent(state["input_paths"], outputs["bronze_sttm"], run_id)
            silver = run_sttm_generator(outputs["profile"], "silver", state.get("business_intent", ""), run_id, prev_sttm_path=outputs["bronze_sttm"])
            return {"phase_outputs": {**outputs, "bronze_parquet": bronze, "silver_sttm": silver}, "current_phase": "hitl_silver"}

        def phase_3(state: dict) -> dict:
            run_id = state["identity"]
            outputs = state["phase_outputs"]
            silver = run_silver_agent(outputs["bronze_parquet"], outputs["silver_sttm"], run_id)
            gold = run_sttm_generator(outputs["profile"], "gold", state.get("business_intent", ""), run_id, silver_parquet_path=silver)
            return {"phase_outputs": {**outputs, "silver_parquet": silver, "gold_sttm": gold}, "current_phase": "hitl_gold"}

        def phase_4(state: dict) -> dict:
            outputs = state["phase_outputs"]
            gold = run_gold_agent([outputs["silver_parquet"]], outputs["gold_sttm"], state["identity"])
            return {"phase_outputs": {**outputs, "gold_parquet": gold}, "current_phase": "gold_data_ready"}

        def approval_gate(layer: str):
            def gate(state: dict) -> dict:
                decision = interrupt({"layer": layer, "sttm_path": state["phase_outputs"][f"{layer}_sttm"]})
                approved = decision if isinstance(decision, bool) else bool(decision.get("approved"))
                return {"approval_flags": {**state.get("approval_flags", {}), layer: approved}}

            return gate

        def route(layer: str, approved_node: str, retry_node: str):
            def select(state: dict) -> str:
                return approved_node if state.get("approval_flags", {}).get(layer) else retry_node

            return select

        builder = StateGraph(dict)
        builder.add_node("phase_1", phase_1)
        builder.add_node("hitl_bronze", approval_gate("bronze"))
        builder.add_node("phase_2", phase_2)
        builder.add_node("hitl_silver", approval_gate("silver"))
        builder.add_node("phase_3", phase_3)
        builder.add_node("hitl_gold", approval_gate("gold"))
        builder.add_node("phase_4", phase_4)
        builder.add_edge(START, "phase_1")
        builder.add_edge("phase_1", "hitl_bronze")
        builder.add_edge("phase_2", "hitl_silver")
        builder.add_edge("phase_3", "hitl_gold")
        builder.add_edge("phase_4", END)
        builder.add_conditional_edges("hitl_bronze", route("bronze", "phase_2", "phase_1"), {"phase_1": "phase_1", "phase_2": "phase_2"})
        builder.add_conditional_edges("hitl_silver", route("silver", "phase_3", "phase_2"), {"phase_2": "phase_2", "phase_3": "phase_3"})
        builder.add_conditional_edges("hitl_gold", route("gold", "phase_4", "phase_3"), {"phase_3": "phase_3", "phase_4": "phase_4"})
        return builder.compile(checkpointer=MemorySaver())

    def start_pipeline(self, csv_paths: list[str], business_intent: str, run_id: str | None = None) -> PipelineState:
        """Start a run through profiling and Bronze STTM review."""
        if not csv_paths:
            raise ValueError("At least one CSV path is required")
        run_id = run_id or uuid4().hex[:12]
        profile = run_profiler(csv_paths[0], business_intent, run_id)
        sttm = run_sttm_generator(profile, "bronze", business_intent, run_id)
        state = PipelineState(
            identity=run_id,
            business_intent=business_intent,
            input_paths=[str(path) for path in csv_paths],
            current_phase="hitl_bronze",
            phase_outputs={"profile": profile, "bronze_sttm": sttm},
        )
        self.states[run_id] = state
        return state

    def _advance(self, state: PipelineState, layer: str) -> PipelineState:
        """Run the transformation and STTM generation after an approval."""
        run_id = state.identity
        if layer == "bronze":
            state.phase_outputs["bronze_parquet"] = run_bronze_agent(state.input_paths, state.phase_outputs["bronze_sttm"], run_id)
            state.phase_outputs["silver_sttm"] = run_sttm_generator(state.phase_outputs["profile"], "silver", state.business_intent, run_id, prev_sttm_path=state.phase_outputs["bronze_sttm"])
            state.current_phase = "hitl_silver"
        elif layer == "silver":
            state.phase_outputs["silver_parquet"] = run_silver_agent(state.phase_outputs["bronze_parquet"], state.phase_outputs["silver_sttm"], run_id)
            state.phase_outputs["gold_sttm"] = run_sttm_generator(state.phase_outputs["profile"], "gold", state.business_intent, run_id, silver_parquet_path=state.phase_outputs["silver_parquet"])
            state.current_phase = "hitl_gold"
        elif layer == "gold":
            state.phase_outputs["gold_parquet"] = run_gold_agent([state.phase_outputs["silver_parquet"]], state.phase_outputs["gold_sttm"], run_id)
            state.current_phase = "gold_data_ready"
        else:
            raise ValueError("layer must be bronze, silver, or gold")
        return state

    def approve_sttm(self, run_id: str, layer: str) -> PipelineState:
        """Approve a layer STTM and advance to the next review gate."""
        state = self._get(run_id)
        expected = {"bronze": "hitl_bronze", "silver": "hitl_silver", "gold": "hitl_gold"}
        if layer not in expected or state.current_phase != expected[layer]:
            raise ValueError(f"Run is not waiting for {layer} approval")
        state.approval_flags[layer] = True
        return self._advance(state, layer)

    def reject_sttm(self, run_id: str, layer: str, feedback: str) -> PipelineState:
        """Record reviewer feedback and regenerate the rejected STTM."""
        state = self._get(run_id)
        if layer not in {"bronze", "silver", "gold"}:
            raise ValueError("layer must be bronze, silver, or gold")
        state.rejection_feedback.setdefault(layer, []).append(feedback.strip())
        previous = state.phase_outputs[f"{layer}_sttm"]
        cumulative = "\n".join(state.rejection_feedback[layer])
        if layer == "gold":
            state.phase_outputs["gold_sttm"] = run_sttm_generator(state.phase_outputs["profile"], "gold", state.business_intent, run_id, prev_sttm_path=previous, reviewer_feedback=cumulative, silver_parquet_path=state.phase_outputs["silver_parquet"])
        elif layer == "bronze":
            state.phase_outputs["bronze_sttm"] = run_sttm_generator(state.phase_outputs["profile"], "bronze", state.business_intent, run_id, prev_sttm_path=previous, reviewer_feedback=cumulative)
        else:
            state.phase_outputs["silver_sttm"] = run_sttm_generator(state.phase_outputs["profile"], "silver", state.business_intent, run_id, prev_sttm_path=state.phase_outputs["bronze_sttm"], reviewer_feedback=cumulative)
        state.approval_flags[layer] = False
        return state

    def get_sttm_for_review(self, run_id: str, layer: str):
        """Return the current STTM dataframe for a review gate."""
        import pandas as pd

        state = self._get(run_id)
        if layer not in {"bronze", "silver", "gold"}:
            raise ValueError("layer must be bronze, silver, or gold")
        return pd.read_csv(state.phase_outputs[f"{layer}_sttm"])

    def get_pipeline_state(self, run_id: str) -> PipelineState:
        """Return the current state for a run."""
        return self._get(run_id)

    def generate_report(self, run_id: str) -> str:
        """Generate an on-demand report from Gold artifacts."""
        state = self._get(run_id)
        return run_reporter(state.phase_outputs["gold_parquet"], state.business_intent, run_id)

    def revise_gold(self, run_id: str, feedback: str) -> PipelineState:
        """Regenerate Gold STTM and outputs after requested analysis changes."""
        state = self.reject_sttm(run_id, "gold", feedback)
        state.approval_flags["gold"] = True
        return self._advance(state, "gold")

    def _get(self, run_id: str) -> PipelineState:
        if run_id not in self.states:
            raise KeyError(f"Unknown run_id: {run_id}")
        return self.states[run_id]
