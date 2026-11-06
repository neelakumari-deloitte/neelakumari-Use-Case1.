"""Schema-driven Gold aggregations."""

from pathlib import Path
import re

import pandas as pd

from core.config import GOLD_DIR


def _amount(frame: pd.DataFrame) -> pd.Series:
	candidates = [column for column in frame.columns if column.lower() in {"total_amount", "total_amount_calculated", "revenue", "sales", "amount"}]
	if candidates:
		return pd.to_numeric(frame[candidates[0]], errors="coerce").fillna(0)
	numeric = [column for column in frame.columns if pd.api.types.is_numeric_dtype(frame[column])]
	unit = next((column for column in numeric if "price" in column.lower()), None)
	quantity = next((column for column in numeric if "quant" in column.lower() or column.lower() in {"qty", "units"}), None)
	if unit and quantity:
		return frame[unit].fillna(0) * frame[quantity].fillna(0)
	return pd.Series(0, index=frame.index, dtype=float)


def _dimension(frame: pd.DataFrame) -> str | None:
	ignored = {"_run_id", "_source_file", "_ingested_at"}
	for column in frame.columns:
		if column.lower() not in ignored and (frame[column].dtype == "object" or "category" in column.lower()):
			return column
	return None


def run_gold_agent(silver_parquet_paths: list[str | Path], sttm_gold_path: str | Path, run_id: str) -> list[str]:
	"""Generate schema-driven revenue, trend, and customer Gold tables."""
	frame = pd.concat([pd.read_parquet(path) for path in silver_parquet_paths], ignore_index=True)
	frame["_amount_for_gold"] = _amount(frame)
	outputs: list[str] = []
	dimension = _dimension(frame)
	if dimension:
		table = frame.groupby(dimension, dropna=False)["_amount_for_gold"].sum().reset_index(name="revenue")
		table["_run_id"] = run_id
		outputs.append(_write(table, "revenue_by_dimension", run_id))
	date_column = next((column for column in frame.columns if "date" in column.lower()), None)
	if date_column:
		dates = pd.to_datetime(frame[date_column], errors="coerce")
		table = frame.assign(_month=dates.dt.to_period("M").astype(str)).groupby("_month")["_amount_for_gold"].sum().reset_index(name="revenue")
		table["_run_id"] = run_id
		outputs.append(_write(table, "monthly_trend", run_id))
	customer = next((column for column in frame.columns if "customer" in column.lower() or column.lower() in {"client_id", "buyer_id"}), None)
	if customer:
		table = frame.groupby(customer, dropna=False)["_amount_for_gold"].sum().reset_index(name="revenue").sort_values("revenue", ascending=False).head(10)
		table["_run_id"] = run_id
		outputs.append(_write(table, "top_customers", run_id))
	if not outputs:
		table = pd.DataFrame({"revenue": [float(frame["_amount_for_gold"].sum())], "_run_id": [run_id]})
		outputs.append(_write(table, "revenue_summary", run_id))
	return outputs


def _write(frame: pd.DataFrame, name: str, run_id: str) -> str:
	output = Path(GOLD_DIR) / f"gold_{name}_{run_id}.parquet"
	frame.to_parquet(output, index=False)
	return str(output)
