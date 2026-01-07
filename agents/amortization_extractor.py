"""
Amortization extraction agent using Gemini LLM and embeddings.
Used for quarterly filings and annual filings only.
Earnings announcements use the separate GAAP reconciliation extractor.
"""

from __future__ import annotations

import json
import re

from agents.extractor_utils import call_llm_and_parse_json
from app.utils.document_section_finder import collect_top_chunk_texts
from app.utils.gemini_client import generate_content_safe
from app.utils.line_item_utils import normalize_line_name


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
            warnings.append(f"Duplicate amortization line item: {name}")
        else:
            seen[normalized] = item

    return list(seen.values()), warnings


def extract_amortization_llm(text: str, time_period: str) -> dict:
    prompt = f"""Extract all amortization line items from the following document text for the time period: {time_period}.

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY extract values that are EXPLICITLY shown in the document text below
- DO NOT invent, infer, calculate, estimate, or approximate any values
- DO NOT create line items that do not appear in the document
- If a value is not visible in the document text, use null
- Extract line items ONLY from amortization-related sections in the document text

Return a JSON object with the following structure:
{{
  "line_items": [
    {{
      "line_name": "exact name as it appears in the document",
      "line_value": numeric value (as number, not string),
      "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (null if not stated),
      "is_operating": true or false,
      "category": "operating" or "non-operating"
    }}
  ]
}}

Classification guidance:
- Non-operating examples: amortization of acquired intangibles, amortization of financing costs
- Operating examples: amortization of capitalized sales costs, amortization of capitalized software
- Default to operating unless explicitly financial or acquisition-related

Document text:
{text[:30000]}

Return only valid JSON, no additional text."""

    return call_llm_and_parse_json(prompt, temperature=0.0)


def extract_amortization_llm_with_feedback(
    text: str, time_period: str, validation_errors: list[str]
) -> dict:
    errors_text = "\n".join(f"- {error}" for error in validation_errors)
    prompt = f"""Extract all amortization line items from the following document text for the time period: {time_period}.

Previous extraction had these validation issues:
{errors_text}

Re-check the text carefully and ensure all amortization line items are included exactly as shown.

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY extract values that are EXPLICITLY shown in the document text below
- DO NOT invent, infer, calculate, estimate, or approximate any values
- DO NOT create line items that do not appear in the document
- If a value is not visible in the document text, use null
- Extract line items ONLY from amortization-related sections in the document text

Return a JSON object with the following structure:
{{
  "line_items": [
    {{
      "line_name": "exact name as it appears in the document",
      "line_value": numeric value (as number, not string),
      "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (null if not stated),
      "is_operating": true or false,
      "category": "operating" or "non-operating"
    }}
  ]
}}

Document text:
{text[:30000]}

Return only valid JSON, no additional text."""

    return call_llm_and_parse_json(prompt, temperature=0.0)


def extract_amortization(
    document_id: str,
    file_path: str,
    time_period: str,
    max_retries: int = 2,
) -> dict:
    """
    Extract amortization line items from document.

    This extractor is used for quarterly filings and annual filings only.
    Earnings announcements use the separate GAAP reconciliation extractor.

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        time_period: Time period (e.g., "Q3 2024")
        max_retries: Maximum number of retry attempts

    Returns:
        Dictionary with extraction results
    """
    # Use general amortization search approach
    query_texts = ["amortize", "amortization", "reconciliation"]
    text, chunk_index, _ = collect_top_chunk_texts(
        document_id=document_id,
        file_path=file_path,
        query_texts=query_texts,
        pages_before=0,
        pages_after=0,
        rerank_top_k=3,
        top_k=3,
        score_threshold=0.25,
    )

    if not text:
        return {
            "line_items": [],
            "chunk_index": None,
            "is_valid": False,
            "validation_errors": ["No amortization section found"],
        }

    validation_errors: list[str] = []
    extraction = extract_amortization_llm(text, time_period)
    line_items = extraction.get("line_items", []) if isinstance(extraction, dict) else []

    line_items, dedup_warnings = _deduplicate_line_items(line_items)
    validation_errors.extend(dedup_warnings)

    retries = 0
    while retries < max_retries and not line_items:
        retries += 1
        retry_extraction = extract_amortization_llm_with_feedback(
            text, time_period, validation_errors
        )
        line_items = (
            retry_extraction.get("line_items", []) if isinstance(retry_extraction, dict) else []
        )
        line_items, dedup_warnings = _deduplicate_line_items(line_items)
        validation_errors.extend(dedup_warnings)

    is_valid = bool(line_items)
    if not line_items:
        validation_errors.append("No amortization line items extracted")

    return {
        "line_items": line_items,
        "chunk_index": chunk_index,
        "is_valid": is_valid,
        "validation_errors": validation_errors,
    }
