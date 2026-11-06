"""Agent execution trace capture."""

import json
import time
from pathlib import Path
from typing import Any

from .config import TRACES_DIR


class AgentTrace:
	"""Capture inputs, plans, tools, verification, output, and status."""

	def __init__(self, agent: str, run_id: str, directory: str | Path = TRACES_DIR) -> None:
		self.agent = agent
		self.run_id = run_id
		self.directory = Path(directory)
		self.started = time.perf_counter()
		self.data: dict[str, Any] = {
			"agent": agent, "run_id": run_id, "input": {}, "plan_steps": [],
			"tool_calls": [], "verification_steps": [], "output": {},
			"status": "running",
		}

	def add_trace(self, category: str, value: Any) -> None:
		"""Append a value to a trace category or replace scalar output fields."""
		if category in {"input", "output", "status"}:
			self.data[category] = value
		else:
			self.data.setdefault(category, []).append(value)

	def save_trace(self, output: Any = None, status: str = "complete") -> str:
		"""Persist the trace JSON and return its path."""
		if output is not None:
			self.data["output"] = output
		self.data["status"] = status
		self.data["duration_seconds"] = round(time.perf_counter() - self.started, 6)
		path = self.directory / f"trace_{self.agent}_{self.run_id}.json"
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(json.dumps(self.data, indent=2, default=str), encoding="utf-8")
		return str(path)
