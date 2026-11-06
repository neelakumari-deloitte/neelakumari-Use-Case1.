"""Central application configuration and data-directory bootstrap."""

import os
from pathlib import Path

try:
	from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is present in normal installs
	def load_dotenv(*args: object, **kwargs: object) -> bool:
		"""Provide a no-op fallback for minimal offline environments."""
		return False

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")
DATA_DIR = BASE_DIR / "data"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"
PROFILES_DIR = DATA_DIR / "profiles"
REPORTS_DIR = DATA_DIR / "reports"
TRACES_DIR = DATA_DIR / "traces"
STTM_DIR = DATA_DIR / "sttm"
STTM_BRONZE = STTM_DIR / "bronze"
STTM_SILVER = STTM_DIR / "silver"
STTM_GOLD = STTM_DIR / "gold"
UPLOADS_DIR = DATA_DIR / "uploads"
CHROMA_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", str(DATA_DIR / "chroma")))

for _directory in (
	DATA_DIR, BRONZE_DIR, SILVER_DIR, GOLD_DIR, PROFILES_DIR, REPORTS_DIR,
	TRACES_DIR, STTM_BRONZE, STTM_SILVER, STTM_GOLD, UPLOADS_DIR, CHROMA_DIR,
):
	_directory.mkdir(parents=True, exist_ok=True)

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OPENAI_API_KEY = GITHUB_TOKEN or os.getenv("OPENAI_API_KEY")
if CLAUDE_API_KEY:
	LLM_PROVIDER = "claude"
	LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5")
	LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
elif GITHUB_TOKEN:
	LLM_PROVIDER = "openai_compatible"
	LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
	LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://models.inference.ai.azure.com")
else:
	LLM_PROVIDER = os.getenv("LLM_PROVIDER", "offline")
	LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
	LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Keep imports and tests portable while exposing the historical string-like API.
for _name in ("BASE_DIR", "DATA_DIR", "BRONZE_DIR", "SILVER_DIR", "GOLD_DIR", "PROFILES_DIR", "REPORTS_DIR", "TRACES_DIR", "STTM_DIR", "STTM_BRONZE", "STTM_SILVER", "STTM_GOLD", "UPLOADS_DIR", "CHROMA_DIR"):
	globals()[_name] = str(globals()[_name])
