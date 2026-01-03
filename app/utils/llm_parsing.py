"""
Helpers for parsing structured LLM responses.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any


def strip_code_fences(response_text: str) -> str:
    """Strip markdown code fences from an LLM response if present."""
    text = response_text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1]
        else:
            text = parts[-1]
        text = text.strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return text


def parse_json_response(
    response_text: str,
    *,
    fallback: dict[str, Any] | None = None,
    required_keys: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Parse an LLM JSON response, returning fallback when parsing or validation fails."""
    cleaned_text = strip_code_fences(response_text)
    try:
        parsed = json.loads(cleaned_text)
    except json.JSONDecodeError:
        return dict(fallback) if fallback is not None else {}

    if not isinstance(parsed, dict):
        return dict(fallback) if fallback is not None else {}

    if required_keys and any(key not in parsed for key in required_keys):
        return dict(fallback) if fallback is not None else {}

    if fallback is None:
        return parsed

    merged = dict(fallback)
    merged.update(parsed)
    return merged
