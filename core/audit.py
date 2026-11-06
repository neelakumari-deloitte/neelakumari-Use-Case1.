"""Append-only JSONL audit logging."""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import TRACES_DIR


class AuditLogger:
	"""Write thread-safe, append-only events for one pipeline run."""

	def __init__(self, run_id: str, directory: str | Path = TRACES_DIR) -> None:
		self.run_id = run_id
		self.path = Path(directory) / f"audit_{run_id}.jsonl"
		self._lock = threading.Lock()

	def log_event(self, agent: str, phase: str, event: str, details: Any = None) -> None:
		"""Append one structured event to the run audit file."""
		entry = {
			"run_id": self.run_id,
			"ts": datetime.now(timezone.utc).isoformat(),
			"agent": agent,
			"phase": phase,
			"event": event,
			"details": details if details is not None else {},
		}
		with self._lock:
			self.path.parent.mkdir(parents=True, exist_ok=True)
			with self.path.open("a", encoding="utf-8") as handle:
				handle.write(json.dumps(entry, default=str) + "\n")
