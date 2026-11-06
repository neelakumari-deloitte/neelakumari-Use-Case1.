"""Bronze ingestion and STTM transformation agent."""

from datetime import datetime, timezone
from pathlib import Path
import re

import pandas as pd

from core.config import BRONZE_DIR


def _rule_map(sttm_path: str | Path) -> dict[str, str]:
	table = pd.read_csv(sttm_path)
	names = {str(column).lower(): column for column in table.columns}
	source = names.get("source_column") or names.get("source") or names.get("column")
	rule = names.get("transformation_rule") or names.get("rule") or names.get("transformation")
	if not source or not rule:
		return {}
	return {str(row[source]): str(row[rule]).lower() for _, row in table.iterrows() if pd.notna(row[source])}


def _apply(value: object, rule: str) -> object:
	if pd.isna(value):
		return value
	text = str(value)
	if "currency" in rule or "strip" in rule and any(symbol in text for symbol in "$€£"):
		text = re.sub(r"[$€£,]", "", text)
	if "numeric" in rule or "number" in rule or "float" in rule:
		return pd.to_numeric(text, errors="coerce")
	if "title" in rule:
		return text.title()
	return value


def run_bronze_agent(csv_paths: list[str | Path], sttm_bronze_path: str | Path, run_id: str) -> list[str]:
	"""Apply Bronze STTM rules to CSV inputs and write parquet artifacts."""
	rules = _rule_map(sttm_bronze_path)
	outputs: list[str] = []
	for csv_path in csv_paths:
		frame = pd.read_csv(csv_path)
		for column, rule in rules.items():
			if column in frame.columns:
				frame[column] = frame[column].map(lambda value: _apply(value, rule))
		frame["_source_file"] = str(csv_path)
		frame["_ingested_at"] = datetime.now(timezone.utc).isoformat()
		frame["_run_id"] = run_id
		output = Path(BRONZE_DIR) / f"{Path(csv_path).stem}_{run_id}.parquet"
		frame.to_parquet(output, index=False)
		outputs.append(str(output))
	return outputs
