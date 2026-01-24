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


def classify_non_operating_items(
    document_id: str,
    file_path: str,
    balance_sheet_data: dict,
    time_period: str | None = None,
    **kwargs,
) -> dict:
    """
    Classify non-operating items using CSV lookup.

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        balance_sheet_data: Dictionary containing balance sheet items
        time_period: Current time period
        **kwargs: Catch-all for extra arguments

    Returns:
        Dictionary with 'line_items' key containing list of classified items
    """
    items = balance_sheet_data.get("line_items", [])
    if not items:
        return {"line_items": []}

    # Load the category mapping
    category_mapping = load_nonoperating_category_mapping()

    # Filter to only include non-operating, non-calculated items
    # Note: In the new pipeline, these flags should have been set during extraction/standardization
    filtered_items = []
    for item in items:
        # If is_operating or is_calculated is not in the item, we include it for lookup
        # to be safe, as it might be a new item that needs classification.
        # However, if they ARE present and True, we skip them.

        is_operating = item.get("is_operating")
        is_calculated = item.get("is_calculated")

        if is_operating is True:
            continue
        if is_calculated is True:
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

    return {"line_items": results}
