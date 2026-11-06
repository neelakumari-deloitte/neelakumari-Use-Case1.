"""Standalone HTML report generation from Gold parquet artifacts."""

from pathlib import Path
import html

import pandas as pd
import plotly.express as px

from core.config import REPORTS_DIR
from core.memory import VectorMemory


def run_reporter(gold_parquet_paths: list[str], business_intent: str, run_id: str) -> str:
	"""Load Gold tables, create heuristic charts, and write an HTML report."""
	sections = ["<html><head><meta charset='utf-8'><title>Retail Medallion Report</title></head><body>", f"<h1>{html.escape(business_intent or 'Retail analysis')}</h1>"]
	summaries = []
	for path in gold_parquet_paths:
		frame = pd.read_parquet(path)
		name = Path(path).stem
		numeric = list(frame.select_dtypes(include="number").columns)
		categorical = [column for column in frame.columns if column not in numeric and not column.startswith("_")]
		if numeric:
			value = numeric[0]
			if categorical:
				chart = px.bar(frame, x=categorical[0], y=value, title=name)
			else:
				chart = px.line(frame, y=value, title=name)
			sections.append(chart.to_html(full_html=False, include_plotlyjs="cdn"))
			summaries.append(f"{name}: {value} total {frame[value].sum():.2f}")
		sections.append(f"<h2>{html.escape(name)}</h2>{frame.head(10).to_html(index=False)}")
	summary = "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in summaries) + "</ul>"
	sections.insert(2, summary)
	sections.append("</body></html>")
	output = Path(REPORTS_DIR) / f"report_{run_id}.html"
	output.write_text("\n".join(sections), encoding="utf-8")
	try:
		VectorMemory().store_report("; ".join(summaries), {"run_id": run_id})
	except Exception:
		pass
	return str(output)
