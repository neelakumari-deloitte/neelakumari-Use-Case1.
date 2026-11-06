"""Silver cleansing, derivation, and deduplication agent."""

from pathlib import Path
import re

import pandas as pd

from core.config import SILVER_DIR


def _numeric(series: pd.Series) -> pd.Series:
	return pd.to_numeric(series.astype(str).str.replace(r"[$€£,]", "", regex=True), errors="coerce")


def run_silver_agent(bronze_parquet_paths: list[str | Path], sttm_silver_path: str | Path, run_id: str) -> str:
	"""Combine Bronze parquet files, derive quality fields, and write Silver parquet."""
	if not bronze_parquet_paths:
		raise ValueError("At least one Bronze parquet path is required")
	frame = pd.concat([pd.read_parquet(path) for path in bronze_parquet_paths], ignore_index=True)
	for column in frame.columns:
		if "date" in column.lower() or "time" in column.lower():
			parsed = pd.to_datetime(frame[column], errors="coerce", format="mixed")
			frame[column] = parsed.dt.strftime("%Y-%m-%d")
	amount_candidates = [column for column in frame.columns if column.lower() in {"amount", "total_amount", "revenue", "sales_amount"}]
	quantity = next((column for column in frame.columns if "quantity" in column.lower() or column.lower() in {"qty", "units"}), None)
	unit_price = next((column for column in frame.columns if "unit" in column.lower() and "price" in column.lower()), None)
	if unit_price and quantity:
		frame["total_amount_calculated"] = _numeric(frame[unit_price]) * _numeric(frame[quantity])
	elif amount_candidates:
		frame["total_amount_calculated"] = _numeric(frame[amount_candidates[0]])
	if "total_amount" in frame.columns and "total_amount_calculated" in frame.columns:
		frame["amount_variance_flag"] = (_numeric(frame["total_amount"]) - frame["total_amount_calculated"]).abs() > 0.01
	order_date = next((column for column in frame.columns if "order" in column.lower() and "date" in column.lower()), None)
	ship_date = next((column for column in frame.columns if "ship" in column.lower() and "date" in column.lower()), None)
	if order_date and ship_date:
		frame["days_to_ship"] = (pd.to_datetime(frame[ship_date], errors="coerce") - pd.to_datetime(frame[order_date], errors="coerce")).dt.days
	order_id = next((column for column in frame.columns if column.lower() == "order_id"), None)
	if order_id:
		frame = frame.drop_duplicates(subset=[order_id], keep="last")
	frame["_run_id"] = run_id
	output = Path(SILVER_DIR) / f"silver_{run_id}.parquet"
	frame.to_parquet(output, index=False)
	return str(output)
