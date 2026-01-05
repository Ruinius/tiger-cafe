"""
Utility helpers for line item normalization and deduplication.
"""

from __future__ import annotations

import re


def normalize_line_name(line_name: str) -> str:
    normalized = line_name.lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def extract_original_name_from_standardized(line_name: str) -> str | None:
    match = re.search(r"\((.+)\)$", line_name)
    if match:
        return match.group(1).strip()
    return None


def deduplicate_non_operating_items(items: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for item in items:
        name = item.get("line_name", "")
        normalized = normalize_line_name(name)
        if normalized in seen:
            existing = seen[normalized]
            existing_score = sum(
                1 for field in ("line_value", "unit", "source") if existing.get(field) is not None
            )
            new_score = sum(
                1 for field in ("line_value", "unit", "source") if item.get(field) is not None
            )
            if new_score > existing_score:
                seen[normalized] = item
        else:
            seen[normalized] = item
    return list(seen.values())
