# Retail Medallion Pipeline

This project profiles uploaded CSV data, generates a source-to-target mapping (STTM), and moves data through Bronze, Silver, and Gold parquet layers. Each STTM stage pauses for human approval. Gold outputs feed an on-demand Plotly HTML report, while audit and agent trace artifacts are written for every run.

## Architecture

```text
CSV -> profiler -> Bronze STTM -> [approve] -> Bronze parquet
									  |
						 Silver STTM -> [approve] -> Silver parquet
									  |
						   Gold STTM -> [approve] -> Gold tables -> HTML report
```

## Setup

Use Python 3.11 or newer:

```text
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

The default provider is `offline`, which gives deterministic semantic suggestions and allows the complete sample workflow to run without network access. Set `CLAUDE_API_KEY` or `ANTHROPIC_API_KEY` for Anthropic, `GITHUB_TOKEN` for the OpenAI-compatible endpoint, or `OPENAI_API_KEY` for OpenAI.

## Run

```text
python -m streamlit run streamlit_app.py --server.port 8501 --server.fileWatcherType none
```

Upload `sample_orders.csv`, enter an intent, and use Analyze file to view three suggestions. Run the pipeline and approve or reject each STTM. Rejection feedback is retained and used for the next generation. After Gold approval, generate the report.

## Artifacts

- `data/profiles`: profile JSON files
- `data/sttm/<layer>`: Bronze, Silver, and Gold mappings
- `data/bronze`, `data/silver`, `data/gold`: parquet outputs
- `data/reports`: standalone HTML reports
- `data/traces`: audit JSONL and agent trace JSON files

## Environment

Provider precedence is Anthropic, then GitHub-compatible OpenAI, then OpenAI/offline. Model IDs vary by account. A model-not-found 404 means set `LLM_MODEL` to an accessible model. For `claude-sonnet-5`, the Anthropic request intentionally omits `temperature`.

## Tests

```text
pytest -q
```

Tests use temporary files and offline provider behavior. Live provider tests should be enabled only when credentials are present. The project targets at least 80 percent coverage.

## Troubleshooting

- Missing optional packages: activate the virtual environment and rerun `pip install -r requirements.txt`.
- Provider errors: use `LLM_PROVIDER=offline` to validate transformations without a key, then check the selected model and base URL.
- Empty outputs: confirm the uploaded file is a readable CSV and that the Gold input contains at least one numeric measure or unit price and quantity pair.

