"""Provider adapters and robust JSON extraction for agent prompts."""

import json
import logging
import re
from typing import Any

from core.config import CLAUDE_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_PROVIDER, LLM_TEMPERATURE, OPENAI_API_KEY

LOGGER = logging.getLogger(__name__)


def extract_json(text: str, expected: str = "object") -> Any:
    """Extract a JSON object or array from plain or wrapped model output."""
    if not isinstance(text, str):
        raise ValueError("Model response must be text")
    decoder = json.JSONDecoder()
    starts = ["[", "{"] if expected == "array" else ["{", "["]
    for start in starts:
        position = text.find(start)
        while position >= 0:
            try:
                value, _ = decoder.raw_decode(text[position:])
                if expected == "array" and isinstance(value, list):
                    return value
                if expected == "object" and isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                pass
            position = text.find(start, position + 1)
    raise ValueError(f"No JSON {expected} found in model response")


def offline_semantics(columns: list[str]) -> dict[str, str]:
    """Return deterministic semantic descriptions for offline execution."""
    return {column: re.sub(r"[_-]+", " ", column).strip().title() for column in columns}


def complete_json(prompt: str, schema: str = "object", columns: list[str] | None = None) -> Any:
    """Call the configured provider and parse structured JSON, with offline fallback."""
    def offline_result() -> Any:
        if schema == "array":
            return ["Revenue and order performance", "Customer and product trends", "Fulfillment and shipping efficiency"]
        return {"semantic_meanings": offline_semantics(columns or [])}

    if LLM_PROVIDER.lower() == "offline" or not (OPENAI_API_KEY or CLAUDE_API_KEY):
        return offline_result()
    try:
        if LLM_PROVIDER.lower() == "claude":
            import anthropic
            client = anthropic.Anthropic(api_key=CLAUDE_API_KEY, base_url=LLM_BASE_URL or None)
            kwargs = {"model": LLM_MODEL, "max_tokens": 2000, "messages": [{"role": "user", "content": prompt}]}
            if LLM_MODEL != "claude-sonnet-5":
                kwargs["temperature"] = LLM_TEMPERATURE
            response = client.messages.create(**kwargs)
            text = "".join(getattr(item, "text", "") for item in response.content)
        else:
            from langchain_openai import ChatOpenAI
            client = ChatOpenAI(model=LLM_MODEL, temperature=LLM_TEMPERATURE, api_key=OPENAI_API_KEY, base_url=LLM_BASE_URL or None)
            response = client.invoke(prompt)
            text = getattr(response, "content", str(response))
    except Exception as exc:
        message = str(exc).lower()
        connection_failure = any(token in message for token in ("connection error", "connecterror", "ssl", "timed out", "timeout"))
        if not connection_failure:
            raise
        LOGGER.warning("Provider connection failed; using deterministic offline response: %s", exc)
        return offline_result()
    return extract_json(text, expected=schema)
