"""Input inspection and data-quality profiling."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from core.audit import AuditLogger
from core.config import PROFILES_DIR
from core.observability import AgentTrace

from .provider import complete_json


def inspect_files(file_path: str | Path) -> dict[str, Any]:
	"""Inspect a CSV and return shape, schema, samples, and missing counts."""
	path = Path(file_path)
	if not path.is_file():
		raise FileNotFoundError(f"Input file does not exist: {path}")
	frame = pd.read_csv(path)
	return {
		"file_path": str(path),
		"shape": [int(frame.shape[0]), int(frame.shape[1])],
		"columns": list(frame.columns),
		"dtypes": {column: str(dtype) for column, dtype in frame.dtypes.items()},
		"sample_values": frame.head(5).fillna("").to_dict(orient="records"),
		"missing_counts": {column: int(value) for column, value in frame.isna().sum().items()},
	}


def _quality_flags(series: pd.Series) -> list[str]:
	values = series.dropna().astype(str)
	flags: list[str] = []
	if values.str.contains(r"^\s*[$€£]|,\d{2}$", regex=True).any():
		flags.append("currency_formatted")
	formats = set()
	for value in values:
		if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
			formats.add("iso")
		elif re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", value.strip()):
			formats.add("slash")
		elif re.fullmatch(r"\d{1,2}-\d{1,2}-\d{4}", value.strip()):
			formats.add("dash")
	if len(formats) > 1:
		flags.append("mixed_date_formats")
	return flags


def profiler_tool(file_path: str | Path) -> dict[str, Any]:
	"""Return per-column statistics and deterministic quality flags."""
	frame = pd.read_csv(file_path)
	columns: dict[str, Any] = {}
	for name in frame.columns:
		series = frame[name]
		columns[name] = {
			"dtype": str(series.dtype),
			"non_null": int(series.notna().sum()),
			"unique": int(series.nunique(dropna=True)),
			"min": series.min() if pd.api.types.is_numeric_dtype(series) else None,
			"max": series.max() if pd.api.types.is_numeric_dtype(series) else None,
			"quality_flags": _quality_flags(series),
		}
	return {"columns": columns, "quality_notes": [flag for item in columns.values() for flag in item["quality_flags"]]}


def run_profiler(file_path: str | Path, business_intent: str, run_id: str) -> str:
	"""Profile an input file, enrich semantics, and write a JSON artifact."""
	inspection = inspect_files(file_path)
	stats = profiler_tool(file_path)
	semantics = complete_json(f"Describe these columns for intent {business_intent}: {inspection['columns']}", columns=inspection["columns"])
	result = {**inspection, **stats, "business_intent": business_intent, "semantic_meanings": semantics.get("semantic_meanings", {})}
	output = Path(PROFILES_DIR) / f"profile_{Path(file_path).stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
	output.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
	AuditLogger(run_id).log_event("profiler", "phase_1", "profile_written", {"path": str(output)})
	AgentTrace("profiler", run_id).save_trace(result)
	return str(output)
