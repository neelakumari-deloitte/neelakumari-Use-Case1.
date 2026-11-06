import json
import pytest
from agents.profiler import inspect_files, profiler_tool, run_profiler


def test_profiler_flags_quality(tmp_path):
    path = tmp_path / "mixed.csv"
    path.write_text('amount,date\n"$1,000.00",2024-01-01\n"$2,000.00",01/02/2024\n', encoding="utf-8")
    assert "amount" in inspect_files(path)["columns"]
    flags = profiler_tool(path)["columns"]
    assert "currency_formatted" in flags["amount"]["quality_flags"]
    assert "mixed_date_formats" in flags["date"]["quality_flags"]
    output = run_profiler(path, "sales", "run")
    assert json.loads(open(output, encoding="utf-8").read())["business_intent"] == "sales"


def test_profiler_invalid_file():
    with pytest.raises(FileNotFoundError):
        inspect_files("missing.csv")