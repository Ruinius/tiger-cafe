"""
Non-operating items classification agent using Gemini LLM.
"""

from __future__ import annotations

import json

from app.utils.gemini_client import generate_content_safe
from app.utils.line_item_utils import deduplicate_non_operating_items


def classify_non_operating_items_llm(items: list[dict]) -> list[dict]:
    items_text = "\n".join(
        f"{idx + 1}. {item.get('line_name')} | {item.get('line_value')} | {item.get('unit')} | {item.get('source')}"
        for idx, item in enumerate(items)
    )

    prompt = f"""Classify the following non-operating items into the provided categories.

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY classify the items listed below
- DO NOT invent new items
- Use the exact line_name provided

Categories:
- cash
- short_term_investments
- operating_lease_related
- other_financial_physical_assets
- debt
- other_financial_liabilities
- deferred_tax_assets
- deferred_tax_liabilities
- common_equity
- preferred_equity
- minority_interest
- goodwill_intangibles
- unknown

Return a JSON array with:
[
  {{
    "line_name": "...",
    "category": "one of the categories above"
  }}
]

Items:
{items_text}

Return only valid JSON."""

    response_text = generate_content_safe(prompt, temperature=0.0)
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
        response_text = response_text.strip()
    return json.loads(response_text)


def classify_non_operating_items(items: list[dict]) -> list[dict]:
    if not items:
        return []

    deduped_items = deduplicate_non_operating_items(items)
    classifications = classify_non_operating_items_llm(deduped_items)
    category_map = {item.get("line_name"): item.get("category") for item in classifications}

    results = []
    for item in deduped_items:
        results.append(
            {
                **item,
                "category": category_map.get(item.get("line_name")) or "unknown",
            }
        )
    return results
