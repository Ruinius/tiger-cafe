"""
Utility helpers for line item normalization and deduplication.
"""

from __future__ import annotations

import re


def normalize_line_name(line_name: str | None) -> str:
    if not line_name:
        return ""
    normalized = line_name.lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def extract_original_name_from_standardized(line_name: str) -> str | None:
    match = re.search(r"\((.+)\)$", line_name)
    if match:
        return match.group(1).strip()
    return None


def convert_to_ones(value: float, unit: str | None) -> float:
    """Convert a value with a given unit to ones."""
    if not unit:
        return value

    unit_lower = unit.lower().strip()
    if "thousand" in unit_lower:
        return value * 1000
    elif "million" in unit_lower:
        return value * 1_000_000
    elif "billion" in unit_lower:
        return value * 1_000_000_000
    return value


def convert_from_ones(value: float, target_unit: str | None) -> float:
    """Convert a value from ones to target unit."""
    if not target_unit:
        return value

    unit_lower = target_unit.lower().strip()
    if "thousand" in unit_lower:
        return value / 1000
    elif "million" in unit_lower:
        return value / 1_000_000
    elif "billion" in unit_lower:
        return value / 1_000_000_000
    return value


def deduplicate_non_operating_items(items: list[dict]) -> list[dict]:
    seen: dict[tuple, dict] = {}
    for item in items:
        name = item.get("line_name", "")
        normalized = normalize_line_name(name)
        value = item.get("line_value")

        # Use simple rounding for float comparison stability if needed,
        # but exact match is usually expected for duplicate extraction.
        # casting to str to ensure types don't mess up tuple hashing if mixed (though they shouldn't be)
        key = (normalized, str(value) if value is not None else "None")

        if key in seen:
            existing = seen[key]
            existing_score = sum(
                1 for field in ("unit", "source") if existing.get(field) is not None
            )
            new_score = sum(1 for field in ("unit", "source") if item.get(field) is not None)
            # If scores are equal, we keep existing (stable)
            # If new has more metadata, replace
            if new_score > existing_score:
                seen[key] = item
        else:
            seen[key] = item
    return list(seen.values())
