"""
Non-operating items classification using CSV mapping lookup.
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.utils.line_item_utils import deduplicate_non_operating_items


def load_nonoperating_category_mapping() -> dict[str, str]:
    """
    Load the nonoperating_category mapping from the CSV file.
    Returns a dict mapping standardized_name -> nonoperating_category
    """
    # CSV is now in app/services
    # __file__ = agents/non_operating_classifier.py
    # parent = agents
    # parent.parent = project root
    csv_path = (
        Path(__file__).parent.parent / "app" / "services" / "bs_calculated_operating_mapping.csv"
    )

    mapping = {}
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            standardized_name = row.get("standardized_name", "").strip()
            nonoperating_category = row.get("nonoperating_category", "").strip()

            # Only add if there's a category defined
            if standardized_name and nonoperating_category:
                mapping[standardized_name] = nonoperating_category

    return mapping


def classify_non_operating_items(items: list[dict]) -> list[dict]:
    """
    Classify non-operating items using CSV lookup.

    Args:
        items: List of items with line_name, line_value, unit, source,
               standardized_name, and is_calculated fields

    Returns:
        List of classified items (only non-operating, non-calculated items)
    """
    if not items:
        return []

    # Load the category mapping
    category_mapping = load_nonoperating_category_mapping()

    # Filter to only include non-operating, non-calculated items
    filtered_items = []
    for item in items:
        # Only include if is_operating is explicitly False
        if item.get("is_operating") is not False:
            continue

        # Only include if is_calculated is explicitly False (not True or None)
        if item.get("is_calculated") is not False:
            continue

        filtered_items.append(item)

    # Deduplicate the filtered items
    deduped_items = deduplicate_non_operating_items(filtered_items)

    # Classify using CSV lookup
    results = []
    for item in deduped_items:
        standardized_name = item.get("standardized_name", "").strip()
        category = category_mapping.get(standardized_name, "unknown")

        results.append(
            {
                **item,
                "category": category,
            }
        )

    return results
