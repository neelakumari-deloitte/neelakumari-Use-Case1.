"""Serializable state shared by pipeline phases and LangGraph."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PipelineState:
	"""Represent a pipeline run, its outputs, approvals, and feedback."""

	identity: str
	phase_outputs: dict[str, Any] = field(default_factory=dict)
	approval_flags: dict[str, bool] = field(default_factory=dict)
	rejection_feedback: dict[str, list[str]] = field(default_factory=dict)
	current_phase: str | None = None
	errors: list[str] = field(default_factory=list)
	scratchpad: dict[str, Any] = field(default_factory=dict)
	business_intent: str = ""
	input_paths: list[str] = field(default_factory=list)

	def to_dict(self) -> dict[str, Any]:
		"""Return a JSON-compatible state dictionary."""
		return asdict(self)

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> "PipelineState":
		"""Construct state from a previously serialized dictionary."""
		values = dict(data)
		feedback = values.get("rejection_feedback", {})
		if isinstance(feedback, list):
			feedback = {"bronze": feedback}
		values["rejection_feedback"] = feedback
		return cls(**values)
