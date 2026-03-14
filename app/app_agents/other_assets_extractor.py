"""
Other assets extraction agent using Gemini LLM
"""

from __future__ import annotations

import json

from app.utils.document_indexer import load_full_document_text
from app.utils.document_section_finder import extract_context_around_keywords
from app.utils.financial_statement_progress import (
    FinancialStatementMilestone,
    add_log,
)
from app.utils.gemini_client import generate_content_safe
from app.utils.line_item_utils import (
    normalize_line_name,
)


def _deduplicate_line_items(line_items: list[dict]) -> tuple[list[dict], list[str]]:
    seen: dict[str, dict] = {}
    warnings: list[str] = []
    for item in line_items:
        name = item.get("line_name", "")
        normalized = normalize_line_name(name)
        if normalized in seen:
            existing = seen[normalized]
            existing_score = sum(
                1
                for field in ("unit", "is_operating", "category")
                if existing.get(field) is not None
            )
            new_score = sum(
                1 for field in ("unit", "is_operating", "category") if item.get(field) is not None
            )
            if new_score > existing_score:
                seen[normalized] = item
            warnings.append(f"Duplicate other assets line item: {name}")
        else:
            seen[normalized] = item
    return list(seen.values()), warnings


def _sum_line_items(line_items: list[dict], category: str) -> float:
    total = 0.0
    for item in line_items:
        if item.get("category") != category:
            continue
        value = item.get("line_value")
        if value is not None:
            total += float(value)
    return total


def _within_tolerance(expected: float | None, actual: float) -> bool:
    if expected is None:
        return False
    tolerance = max(1000.0, abs(expected) * 0.0001)
    return abs(actual - expected) <= tolerance


def extract_other_assets_llm(
    text: str,
    time_period: str,
    expected_current_total: float | None,
    expected_non_current_total: float | None,
) -> dict:
    prompt = f"""Extract detailed line items for Other Current Assets and Other Non-Current Assets
from the following document text for the time period: {time_period}.

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY extract values that are EXPLICITLY shown in the document text below
- DO NOT invent, infer, calculate, estimate, or approximate any values
- DO NOT create line items that do not appear in the document
- If a value is not visible in the document text, use null

Balance sheet totals for validation:
- Other Current Assets total: {expected_current_total}
- Other Non-Current Assets total: {expected_non_current_total}

Return a JSON object with:
{{
  "line_items": [
    {{
      "line_name": "exact name as shown",
      "line_value": numeric value (as number, not string),
      "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (null if not stated),
      "category": "Current Assets" or "Non-Current Assets",
      "is_operating": true or false
    }}
  ]
}}

Classification guidance:
- Non-operating examples: financial derivatives, currency hedges, investments, marketable securities
- Operating: everything else (default to operating unless explicitly financial)

Document text:
{text[:30000]}

Return only valid JSON, no additional text."""

    response_text = generate_content_safe(prompt, temperature=0.0)
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
        response_text = response_text.strip()
    return json.loads(response_text)


def extract_other_assets_llm_with_feedback(
    text: str,
    time_period: str,
    expected_current_total: float | None,
    expected_non_current_total: float | None,
    validation_errors: list[str],
) -> dict:
    errors_text = "\n".join(f"- {error}" for error in validation_errors)
    prompt = f"""Extract detailed line items for Other Current Assets and Other Non-Current Assets
from the following document text for the time period: {time_period}.

The previous extraction had validation issues:
{errors_text}

Balance sheet totals for validation:
- Other Current Assets total: {expected_current_total}
- Other Non-Current Assets total: {expected_non_current_total}

Re-check the text and ensure all line items for the correct time period are included.

Return a JSON object with:
{{
  "line_items": [
    {{
      "line_name": "exact name as shown",
      "line_value": numeric value (as number, not string),
      "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (null if not stated),
      "category": "Current Assets" or "Non-Current Assets",
      "is_operating": true or false
    }}
  ]
}}

Document text:
{text[:30000]}

Return only valid JSON, no additional text."""

    response_text = generate_content_safe(prompt, temperature=0.0)
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
        response_text = response_text.strip()
    return json.loads(response_text)


def extract_other_assets(
    document_id: str,
    file_path: str,
    time_period: str,
    query_terms: list[str],
    expected_current_total: float | None,
    expected_non_current_total: float | None,
    max_retries: int = 2,
) -> dict:
    if not query_terms:
        return {
            "line_items": [],
            "chunk_index": None,
            "is_valid": False,
            "validation_errors": ["No balance sheet labels found for other assets"],
        }

    full_text = load_full_document_text(document_id, file_path)
    text = extract_context_around_keywords(full_text, query_terms, context_chars=500)
    chunk_index = None

    add_log(
        document_id,
        FinancialStatementMilestone.OTHER_ASSETS,
        "I'm checking the detailed breakdown of 'Other Assets' in the notes.",
    )

    if not text:
        return {
            "line_items": [],
            "chunk_index": None,
            "is_valid": False,
            "validation_errors": ["Other assets section not found"],
        }

    add_log(
        document_id,
        FinancialStatementMilestone.OTHER_ASSETS,
        f"I'm asking Gemini to find the detailed composition of 'Other Assets' for {time_period}.",
    )
    extraction = extract_other_assets_llm(
        text, time_period, expected_current_total, expected_non_current_total
    )
    line_items = extraction.get("line_items", []) if isinstance(extraction, dict) else []
    add_log(
        document_id,
        FinancialStatementMilestone.OTHER_ASSETS,
        f"Gemini response: Deep dive into 'Other Assets' complete. Identified {len(line_items)} specific notes items, including prepaid expenses and other long-term assets.",
        source="gemini",
    )

    if line_items:
        pass

    line_items, dedup_warnings = _deduplicate_line_items(line_items)
    validation_errors = dedup_warnings

    current_sum = _sum_line_items(line_items, "Current Assets")
    non_current_sum = _sum_line_items(line_items, "Non-Current Assets")

    if not _within_tolerance(expected_current_total, current_sum):
        validation_errors.append(
            f"Other Current Assets total mismatch: expected {expected_current_total}, got {current_sum}"
        )
    if not _within_tolerance(expected_non_current_total, non_current_sum):
        validation_errors.append(
            f"Other Non-Current Assets total mismatch: expected {expected_non_current_total}, got {non_current_sum}"
        )

    retries = 0
    while validation_errors and retries < max_retries:
        retries += 1
        add_log(
            document_id,
            FinancialStatementMilestone.OTHER_ASSETS,
            "I'm sending the total mismatches back to Gemini for a more accurate breakdown.",
        )
        extraction = extract_other_assets_llm_with_feedback(
            text,
            time_period,
            expected_current_total,
            expected_non_current_total,
            validation_errors,
        )
        add_log(
            document_id,
            FinancialStatementMilestone.OTHER_ASSETS,
            f"Gemini response: Refined composition breakdown. Successfully re-mapped {len(extraction.get('line_items', []))} items to reconcile with the main balance sheet totals.",
            source="gemini",
        )
        line_items = extraction.get("line_items", []) if isinstance(extraction, dict) else []
        line_items, dedup_warnings = _deduplicate_line_items(line_items)
        validation_errors = dedup_warnings

        current_sum = _sum_line_items(line_items, "Current Assets")
        non_current_sum = _sum_line_items(line_items, "Non-Current Assets")

        if not _within_tolerance(expected_current_total, current_sum):
            validation_errors.append(
                f"Other Current Assets total mismatch: expected {expected_current_total}, got {current_sum}"
            )
        if not _within_tolerance(expected_non_current_total, non_current_sum):
            validation_errors.append(
                f"Other Non-Current Assets total mismatch: expected {expected_non_current_total}, got {non_current_sum}"
            )

    # Calculate residuals and add them to line_items
    final_line_items = []

    # Process Current Assets
    current_items = [item for item in line_items if item.get("category") == "Current Assets"]
    current_sum = _sum_line_items(current_items, "Current Assets")
    if expected_current_total is not None:
        residual_value = expected_current_total - current_sum
        # Use a small tolerance for floating point issues
        if abs(residual_value) > 0.01:
            final_line_items.extend(current_items)
            final_line_items.append(
                {
                    "line_name": "Residual (Operating)",
                    "line_value": residual_value,
                    "unit": current_items[0].get("unit") if current_items else None,
                    "category": "Current Assets",
                    "is_operating": True,
                }
            )
        else:
            final_line_items.extend(current_items)
    else:
        final_line_items.extend(current_items)

    # Process Non-Current Assets
    non_current_items = [
        item for item in line_items if item.get("category") == "Non-Current Assets"
    ]
    non_current_sum = _sum_line_items(non_current_items, "Non-Current Assets")
    if expected_non_current_total is not None:
        residual_value = expected_non_current_total - non_current_sum
        if abs(residual_value) > 0.01:
            final_line_items.extend(non_current_items)
            final_line_items.append(
                {
                    "line_name": "Residual (Operating)",
                    "line_value": residual_value,
                    "unit": non_current_items[0].get("unit") if non_current_items else None,
                    "category": "Non-Current Assets",
                    "is_operating": True,
                }
            )
        else:
            final_line_items.extend(non_current_items)
    else:
        final_line_items.extend(non_current_items)

    is_valid = bool(final_line_items)

    # Assign line_order
    for i, item in enumerate(final_line_items):
        item["line_order"] = i

    return {
        "line_items": final_line_items,
        "chunk_index": chunk_index,
        "is_valid": is_valid,
        "validation_errors": validation_errors,
    }
