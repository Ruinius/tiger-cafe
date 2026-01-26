"""
Organic growth extraction agent using Gemini LLM and embeddings
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from agents.extractor_utils import call_llm_and_parse_json
from app.utils.document_section_finder import (
    collect_top_chunk_texts,
    find_top_numeric_chunks,
    get_chunk_with_context,
    rank_chunks_by_query,
)
from app.utils.financial_statement_progress import (
    FinancialStatementMilestone,
    add_log,
)
from app.utils.gemini_client import generate_content_safe
from app.utils.line_item_utils import convert_from_ones, convert_to_ones


def find_revenue_line_value(line_items: list[dict]) -> float | None:
    if not line_items:
        return None

    # Use only standardized names to ensure accuracy
    for item in line_items:
        std_name = item.get("standardized_name")
        if std_name in ["total_revenue", "revenue"]:
            return float(item.get("line_value")) if item.get("line_value") is not None else None

    return None


def _normalize_value(value: object) -> float | None:
    """Normalize a value to a float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip().replace(",", "")
        if not stripped:
            return None
        is_negative = stripped.startswith("(") and stripped.endswith(")")
        if is_negative:
            stripped = stripped[1:-1]
        try:
            parsed = float(stripped)
        except ValueError:
            return None
        return -parsed if is_negative else parsed
    return None


def extract_prior_year_revenue(
    text: str,
    time_period: str,
    current_revenue: float | None = None,
    revenue_line_name: str | None = None,
    unit: str | None = None,
    period_end_date: str | None = None,
) -> tuple[float | None, str | None]:
    """
    Extract prior year revenue using LLM with rich context.
    """
    # Determine labels for current and prior periods
    current_label = period_end_date or time_period
    prior_label = None

    # Try to calculate prior period from end date first
    if period_end_date:
        try:
            current_dt = datetime.strptime(period_end_date, "%Y-%m-%d")
            # Determine prior year
            prior_year = current_dt.year - 1
            # Handle Feb 29 for non-leap years
            if current_dt.month == 2 and current_dt.day == 29:
                prior_dt = current_dt.replace(year=prior_year, day=28)
            else:
                prior_dt = current_dt.replace(year=prior_year)
            # Prepend 'Quarter ending in ' for consistency
            prior_label = "Quarter ending in " + prior_dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    # If we couldn't use the end date, fall back to time_period regex
    if not prior_label:
        year_match = re.search(r"(\d{4})", time_period)
        if year_match:
            current_yr = int(year_match.group(1))
            prior_yr = current_yr - 1
            # Prepend 'Quarter ending in ' for more explicit finding
            prior_label = "Quarter ending in " + time_period.replace(str(current_yr), str(prior_yr))
        else:
            # Silently return, the caller will handle logging missing revenue
            return None, None

    # Build context information
    context_info = ""
    if current_revenue is not None:
        context_info = (
            f"\n\nCONTEXT: The current period ({current_label}) revenue is {current_revenue}."
        )
        if revenue_line_name:
            context_info += f' This value is from the line item: "{revenue_line_name}".'
        context_info += f" You are looking for the {prior_label} value from the SAME ROW in the comparative financial statement."

    extraction_prompt = f"""Extract the revenue (or total revenue, or net revenue) for {prior_label} from the following document text.{context_info}

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY extract the value if it is EXPLICITLY shown in the document text below
- DO NOT invent, infer, calculate, estimate, or approximate any values
- Look for revenue line items in comparative columns (prior year columns)
- The value must be from the SAME ROW as the current period revenue in the financial statement table
- The value must be clearly labeled as being for {prior_label}
- If you cannot find the value explicitly stated, return null

Return a JSON object:
{{
    "revenue_prior_year": numeric value for {prior_label} revenue (null if not found),
    "revenue_prior_year_unit": unit - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (null if not found),
    "explanation": "brief explanation of where you found this value in the document (mention the row/line item name)"
}}

Document text:
{{text[:30000]}}

Return only valid JSON, no additional text."""

    try:
        # Use simple f-string formatting since the payload has curly braces
        formatted_prompt = extraction_prompt.replace("{text[:30000]}", text[:30000])
        result = call_llm_and_parse_json(formatted_prompt, temperature=0.0)

        revenue_value = result.get("revenue_prior_year")
        revenue_unit = result.get("revenue_prior_year_unit")
        result.get("explanation", "")

        if revenue_value is None:
            # Silently return
            return None, None

        # add_log(document_id, FinancialStatementMilestone.ORGANIC_GROWTH, f"I found the prior year revenue: {revenue_value} ({revenue_unit}).")
        # Note: document_id is not passed to this helper yet, so we'll log in the main function
        pass
        return revenue_value, revenue_unit

    except Exception:
        return None, None


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
        context_name="Organic Growth",
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
        add_log(
            document_id,
            FinancialStatementMilestone.ORGANIC_GROWTH,
            f"I'm asking Gemini to analyze the section for any acquisition impacts on revenue for {time_period}.",
            source="system",
        )
        extraction = extract_organic_growth_llm(text, time_period)
        if extraction.get("acquisition_flag"):
            add_log(
                document_id,
                FinancialStatementMilestone.ORGANIC_GROWTH,
                f"Gemini response: Acquisition detected with a revenue impact of {extraction.get('acquisition_revenue_impact')} ({extraction.get('acquisition_revenue_impact_unit') or 'ones'}). This will be used to calculate the organic growth rate.",
                source="gemini",
            )
        else:
            add_log(
                document_id,
                FinancialStatementMilestone.ORGANIC_GROWTH,
                "Gemini response: No significant revenue-impacting acquisitions or business combinations were identified in the specified period.",
                source="gemini",
            )

    retries = 0
    while retries < max_retries and not extraction:
        retries += 1
        extraction = extract_organic_growth_llm(text or "", time_period)

    line_items = income_statement_data.get("line_items", [])
    current_unit = income_statement_data.get("unit")
    current_revenue = find_revenue_line_value(line_items)
    prior_revenue = income_statement_data.get("revenue_prior_year")
    prior_revenue_unit = None

    # If using prior_revenue from IS data, assume same unit as IS
    if prior_revenue is not None:
        prior_revenue_unit = current_unit

    # If prior revenue is missing, attempt to extract it from the income statement section
    if current_revenue is not None and prior_revenue is None:
        add_log(
            document_id,
            FinancialStatementMilestone.ORGANIC_GROWTH,
            "I'm looking for the prior period revenue in the income statement to calculate growth rates.",
        )

        # 1. Find Income Statement section (same logic as IS extractor)
        top_numeric_chunks = find_top_numeric_chunks(
            document_id, file_path, top_k=10, context_name="Income Statement"
        )
        query_texts_is = ["Revenue", "Profit", "Income", "Tax", "Cost"]
        candidate_chunks_is = rank_chunks_by_query(
            document_id,
            file_path,
            top_numeric_chunks,
            query_texts_is,
            context_name="Income Statement",
        )

        if candidate_chunks_is:
            # We'll try the first candidate chunk for the IS
            is_chunk_index = candidate_chunks_is[0]
            is_text, _, _ = get_chunk_with_context(
                document_id, file_path, is_chunk_index, chars_before=2500, chars_after=2500
            )

            # Find the revenue line name used in the IS
            revenue_line_name = None
            for item in line_items:
                if item.get("standardized_name") in ["total_revenue", "revenue"]:
                    revenue_line_name = item.get("line_name")
                    break

            # 2. Extract prior revenue
            add_log(
                document_id,
                FinancialStatementMilestone.ORGANIC_GROWTH,
                "I'm now asking Gemini to find the revenue from the same period last year in the comparative statements.",
            )
            extracted_prior_val, extracted_prior_unit = extract_prior_year_revenue(
                is_text,
                time_period,
                current_revenue,
                revenue_line_name,
                income_statement_data.get("unit"),
                income_statement_data.get("period_end_date"),
            )
            if extracted_prior_val is not None:
                add_log(
                    document_id,
                    FinancialStatementMilestone.ORGANIC_GROWTH,
                    f"Gemini response: Found the comparative revenue figure for the prior year: {extracted_prior_val} ({extracted_prior_unit or 'ones'}). Comparative analysis can now proceed.",
                    source="gemini",
                )
            else:
                add_log(
                    document_id,
                    FinancialStatementMilestone.ORGANIC_GROWTH,
                    "Gemini response: Comparative revenue data for the prior fiscal interval could not be definitively located. Growth calculation will be limited.",
                    source="gemini",
                )

            if extracted_prior_val is not None:
                prior_revenue = extracted_prior_val
                prior_revenue_unit = extracted_prior_unit

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
        # Convert both to ones for safe calculation
        current_rev_ones = convert_to_ones(float(current_revenue), current_unit)
        impact_ones = convert_to_ones(
            float(acquisition_impact), extraction.get("acquisition_revenue_impact_unit")
        )

        # If prior_revenue_unit is None, it might imply it's already in the same unit as the main doc or extracted as a raw number.
        # But if it came from extract_prior_year_revenue, it returns a unit.
        # IF prior_revenue came from income_statement_data.get("revenue_prior_year"), check if unit is already handled.

        # NOTE: extracted_prior_val from extract_prior_year_revenue is raw from LLM.
        # extracted_prior_unit is what the LLM said it is.
        # So conversion to ones IS needed.
        prior_rev_ones = convert_to_ones(float(prior_revenue), prior_revenue_unit)

        if prior_rev_ones != 0:
            simple_growth = (current_rev_ones - prior_rev_ones) / prior_rev_ones * 100

            # Adjusted revenue = current - acquisition impact
            adjusted_revenue_ones = current_rev_ones - impact_ones

            organic_growth = (adjusted_revenue_ones - prior_rev_ones) / prior_rev_ones * 100

            # Normalize display values to the current unit
            prior_revenue = convert_from_ones(prior_rev_ones, current_unit)
            acquisition_impact = convert_from_ones(impact_ones, current_unit)
            adjusted_revenue = convert_from_ones(adjusted_revenue_ones, current_unit)

            # Update unit metadata for return
            prior_revenue_unit = current_unit

    is_valid = not validation_errors and current_revenue is not None and prior_revenue is not None

    return {
        "currency": income_statement_data.get("currency"),
        "acquisition_flag": extraction.get("acquisition_flag", False),
        "acquisition_revenue_impact": acquisition_impact,
        "acquisition_revenue_impact_unit": current_unit
        if current_revenue is not None
        else extraction.get("acquisition_revenue_impact_unit"),
        "current_period_revenue": current_revenue,
        "current_period_revenue_unit": current_unit,
        "prior_period_revenue": prior_revenue,
        "prior_period_revenue_unit": prior_revenue_unit,
        "simple_revenue_growth": simple_growth,
        "current_period_adjusted_revenue": adjusted_revenue,
        "current_period_adjusted_revenue_unit": current_unit,
        "organic_revenue_growth": organic_growth,
        "chunk_index": chunk_index,
        "is_valid": is_valid,
        "validation_errors": validation_errors,
    }
