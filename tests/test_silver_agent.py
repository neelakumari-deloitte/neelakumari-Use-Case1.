import pandas as pd

from agents.silver_agent import run_silver_agent


def test_silver_derives_and_deduplicates(tmp_path):
    bronze = tmp_path / "bronze.parquet"
    pd.DataFrame({
        "order_id": [1, 1], "order_date": ["2024-01-01", "2024-01-01"],
        "ship_date": ["2024-01-03", "2024-01-03"], "unit_price": [10, 10], "quantity": [2, 2],
    }).to_parquet(bronze, index=False)
    result = run_silver_agent([bronze], tmp_path / "missing-sttm.csv", "run")
    frame = pd.read_parquet(result)
    assert len(frame) == 1
    assert frame.loc[0, "total_amount_calculated"] == 20
    assert frame.loc[0, "days_to_ship"] == 2
