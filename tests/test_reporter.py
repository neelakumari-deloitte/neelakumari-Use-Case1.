import pandas as pd

from agents.reporter import run_reporter


def test_reporter_html(tmp_path, monkeypatch):
    gold = tmp_path / "gold_revenue_run.parquet"
    pd.DataFrame({"region": ["East", "West"], "revenue": [10, 20], "_run_id": ["run", "run"]}).to_parquet(gold, index=False)
    monkeypatch.setattr("agents.reporter.REPORTS_DIR", str(tmp_path))
    output = run_reporter([str(gold)], "sales performance", "run")
    content = open(output, encoding="utf-8").read()
    assert "sales performance" in content
    assert "plotly" in content.lower()
