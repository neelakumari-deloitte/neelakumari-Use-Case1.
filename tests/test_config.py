from pathlib import Path

from core import config


def test_directories_bootstrapped():
    for name in ("DATA_DIR", "BRONZE_DIR", "SILVER_DIR", "GOLD_DIR", "PROFILES_DIR", "REPORTS_DIR", "TRACES_DIR", "STTM_BRONZE", "STTM_SILVER", "STTM_GOLD", "UPLOADS_DIR", "CHROMA_DIR"):
        assert Path(getattr(config, name)).is_dir()


def test_offline_defaults_are_deterministic():
    assert config.LLM_TEMPERATURE == 0
    assert config.LLM_PROVIDER in {"offline", "openai", "openai_compatible", "claude"}
