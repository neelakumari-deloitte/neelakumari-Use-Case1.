import pandas as pd

from agents.gold_agent import run_gold_agent


def test_gold_generates_schema_tables(tmp_path):
    silver = tmp_path / "silver.parquet"
    pd.DataFrame({
        "customer_id": ["a", "b"], "product_category": ["x", "x"],
        "order_date": ["2024-01-01", "2024-02-01"], "total_amount_calculated": [10, 20],
    }).to_parquet(silver, index=False)
    outputs = run_gold_agent([silver], tmp_path / "gold-sttm.csv", "run")
    assert len(outputs) == 3
    assert all(pd.read_parquet(path)["_run_id"].eq("run").all() for path in outputs)
