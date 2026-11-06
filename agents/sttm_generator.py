"""STTM generation and deterministic layer derivation."""

import json
from pathlib import Path

import pandas as pd

from core.config import STTM_BRONZE, STTM_GOLD, STTM_SILVER
from .provider import complete_json


def _bronze_rows(profile: dict, feedback: str) -> list[dict[str, str]]:
	columns = profile.get("columns", [])
	meanings = profile.get("semantic_meanings", {})
	response = complete_json(f"Create transformation rules for columns {columns}. Feedback: {feedback}", columns=columns)
	semantic = response.get("semantic_meanings", {})
	rows = []
	for column in columns:
		dtype = profile.get("dtypes", {}).get(column, "string")
		rule = "cast_numeric" if "int" in dtype or "float" in dtype else "passthrough"
		flags = profile.get("columns", {}).get(column, {}).get("quality_flags", [])
		if "currency_formatted" in flags:
			rule = "strip_currency_cast_numeric"
		if "date" in column.lower() or "time" in column.lower():
			rule = "normalize_date"
		if any(word in column.lower() for word in ("name", "city", "category")):
			rule = "title_case"
		rows.append({"source_column": column, "target_column": column, "data_type": dtype, "transformation_rule": rule, "description": semantic.get(column, meanings.get(column, column)), "layer": "bronze"})
	rows.extend([
		{"source_column": "_source_file", "target_column": "_source_file", "data_type": "string", "transformation_rule": "metadata", "description": "Input file", "layer": "bronze"},
		{"source_column": "_ingested_at", "target_column": "_ingested_at", "data_type": "datetime", "transformation_rule": "metadata", "description": "Ingestion timestamp", "layer": "bronze"},
		{"source_column": "_run_id", "target_column": "_run_id", "data_type": "string", "transformation_rule": "metadata", "description": "Pipeline run identifier", "layer": "bronze"},
	])
	return rows


def run_sttm_generator(profile_path: str, layer: str, business_intent: str, run_id: str, prev_sttm_path: str = "", reviewer_feedback: str = "", silver_parquet_path: str = "") -> str:
	"""Generate a layer STTM CSV, optionally revising it from reviewer feedback."""
	if layer not in {"bronze", "silver", "gold"}:
		raise ValueError("layer must be bronze, silver, or gold")
	profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))
	if layer == "bronze":
		rows = _bronze_rows(profile, reviewer_feedback)
	elif layer == "silver":
		source_path = Path(prev_sttm_path)
		source = pd.read_csv(source_path)
		rows = source.to_dict(orient="records")
		for row in rows:
			row["layer"] = "silver"
		rows.extend([
			{"source_column": "total_amount_calculated", "target_column": "total_amount_calculated", "data_type": "float", "transformation_rule": "unit_price_times_quantity", "description": "Calculated total", "layer": "silver"},
			{"source_column": "amount_variance_flag", "target_column": "amount_variance_flag", "data_type": "boolean", "transformation_rule": "compare_amounts", "description": "Amount consistency flag", "layer": "silver"},
			{"source_column": "days_to_ship", "target_column": "days_to_ship", "data_type": "integer", "transformation_rule": "ship_date_minus_order_date", "description": "Fulfillment duration", "layer": "silver"},
		])
	else:
		if not silver_parquet_path:
			raise ValueError("silver_parquet_path is required for gold STTM")
		frame = pd.read_parquet(silver_parquet_path)
		columns = [column for column in frame.columns if not column.startswith("_")]
		rows = [{"source_column": column, "target_column": column, "data_type": str(frame[column].dtype), "transformation_rule": "aggregate", "description": "Gold source field", "layer": "gold"} for column in columns]
		rows.extend([
			{"source_column": "revenue_by_dimension", "target_column": "revenue_by_dimension", "data_type": "table", "transformation_rule": "group_amount_by_dimension", "description": "Revenue dimension table", "layer": "gold"},
			{"source_column": "monthly_trend", "target_column": "monthly_trend", "data_type": "table", "transformation_rule": "group_amount_by_month", "description": "Monthly trend table", "layer": "gold"},
			{"source_column": "top_customers", "target_column": "top_customers", "data_type": "table", "transformation_rule": "group_amount_by_customer", "description": "Top customer table", "layer": "gold"},
		])
	output_dir = {"bronze": STTM_BRONZE, "silver": STTM_SILVER, "gold": STTM_GOLD}[layer]
	output = Path(output_dir) / f"sttm_{layer}_{run_id}.csv"
	pd.DataFrame(rows).drop_duplicates(subset=["source_column", "target_column"], keep="last").to_csv(output, index=False)
	return str(output)
