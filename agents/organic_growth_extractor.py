"""
Organic growth extraction agent using Gemini LLM and embeddings
"""

from __future__ import annotations

import json

from app.utils.document_section_finder import collect_top_chunk_texts
from app.utils.gemini_client import generate_content_safe
from app.utils.line_item_utils import normalize_line_name


def find_revenue_line_value(line_items: list[dict]) -> float | None:
    if not line_items:
        return None

    for item in line_items:
        name = item.get("line_name", "").lower()
        if "total net revenue" in name:
            return float(item.get("line_value")) if item.get("line_value") is not None else None

    for item in line_items:
        name = normalize_line_name(item.get("line_name", ""))
        if "total" in name and "revenue" in name:
            return float(item.get("line_value")) if item.get("line_value") is not None else None

    for item in line_items:
        name = normalize_line_name(item.get("line_name", ""))
        if "revenue" in name or "net sales" in name:
            return float(item.get("line_value")) if item.get("line_value") is not None else None

    return None


def extract_organic_growth_llm(text: str, time_period: str) -> dict:
    prompt = f"""Analyze the following document text for the time period: {time_period}.
Determine if the company made acquisitions that impacted revenue for this period.

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY extract values that are EXPLICITLY shown in the document text below
- DO NOT invent, infer, calculate, estimate, or approximate any values
- If no acquisition impact is explicitly stated, set acquisition_revenue_impact to 0 and acquisition_flag to false

Return a JSON object with:
{{
  "acquisition_flag": true or false,
  "acquisition_revenue_impact": number (0 if no acquisition impact is stated),
  "acquisition_revenue_impact_unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (null if not stated)
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


def extract_organic_growth(
    document_id: str,
    file_path: str,
    time_period: str,
    income_statement_data: dict,
    max_retries: int = 1,
) -> dict:
    query_texts = ["merge", "acquire", "acquisition", "m&a", "business combination"]
    text, chunk_index, _ = collect_top_chunk_texts(
        document_id=document_id,
        file_path=file_path,
        query_texts=query_texts,
        chars_before=0,
        chars_after=0,
        rerank_top_k=3,
        top_k=3,
        score_threshold=0.25,
    )

    validation_errors: list[str] = []

    if not text:
        validation_errors.append("Organic growth section not found")
        extraction = {
            "acquisition_flag": False,
            "acquisition_revenue_impact": 0,
            "acquisition_revenue_impact_unit": None,
        }
    else:
        extraction = extract_organic_growth_llm(text, time_period)

    retries = 0
    while retries < max_retries and not extraction:
        retries += 1
        extraction = extract_organic_growth_llm(text or "", time_period)

    line_items = income_statement_data.get("line_items", [])
    current_revenue = find_revenue_line_value(line_items)
    prior_revenue = income_statement_data.get("revenue_prior_year")

    if current_revenue is None:
        validation_errors.append("Current period revenue not found in income statement")
    if prior_revenue is None:
        validation_errors.append("Prior period revenue not found in income statement")

    acquisition_impact = extraction.get("acquisition_revenue_impact")
    if acquisition_impact is None:
        acquisition_impact = 0

    simple_growth = None
    organic_growth = None
    adjusted_revenue = None

    if current_revenue is not None and prior_revenue:
        simple_growth = (current_revenue - float(prior_revenue)) / float(prior_revenue) * 100
        adjusted_revenue = current_revenue - float(acquisition_impact)
        organic_growth = (adjusted_revenue - float(prior_revenue)) / float(prior_revenue) * 100

    is_valid = not validation_errors and current_revenue is not None and prior_revenue is not None

    return {
        "acquisition_flag": extraction.get("acquisition_flag", False),
        "acquisition_revenue_impact": acquisition_impact,
        "acquisition_revenue_impact_unit": extraction.get("acquisition_revenue_impact_unit"),
        "current_period_revenue": current_revenue,
        "prior_period_revenue": prior_revenue,
        "simple_revenue_growth": simple_growth,
        "current_period_adjusted_revenue": adjusted_revenue,
        "organic_revenue_growth": organic_growth,
        "chunk_index": chunk_index,
        "is_valid": is_valid,
        "validation_errors": validation_errors,
    }
