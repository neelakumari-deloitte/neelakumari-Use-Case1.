import pandas as pd

from agents.bronze_agent import run_bronze_agent


def test_run_bronze_agent(tmp_path):
    csv_path = tmp_path / "orders.csv"
    pd.DataFrame({"amount": ["$1,200.00"], "customer_name": ["jane doe"]}).to_csv(csv_path, index=False)
    sttm = tmp_path / "bronze.csv"
    pd.DataFrame({"source_column": ["amount", "customer_name"], "transformation_rule": ["strip_currency_cast_numeric", "title_case"]}).to_csv(sttm, index=False)
    output = run_bronze_agent([csv_path], sttm, "run")
    frame = pd.read_parquet(output[0])
    assert frame.loc[0, "amount"] == 1200
    assert frame.loc[0, "customer_name"] == "Jane Doe"
    assert frame.loc[0, "_run_id"] == "run"

