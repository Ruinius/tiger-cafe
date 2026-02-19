"""
Organic growth extraction agent using Gemini LLM and embeddings
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from agents.extractor_utils import call_llm_and_parse_json, call_llm_with_retry
from app.utils.document_section_finder import (
    collect_top_chunk_texts,
    get_chunk_with_context,
)
from app.utils.financial_statement_progress import (
    FinancialStatementMilestone,
    add_log,
)
from app.utils.gemini_client import generate_content_safe
from app.utils.line_item_utils import convert_to_ones


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


def _reflect_on_prior_revenue(
    original_value: float | None,
    original_unit: str | None,
    current_label: str,
    prior_label: str,
    current_revenue: float | None,
    text: str,  # Added text parameter
) -> tuple[float | None, str | None, str | None]:
    """
    Verify the extracted prior revenue matches the duration of the current period.
    """
    # Reflection prompt updated to enforce unit constraints
    reflection_prompt = f"""You are a QA Auditor.
    1.  The system extracted a prior year revenue of {original_value} for: {prior_label}.
    2.  The current period is: {current_label}.
    3.  The current period revenue is: {current_revenue}.

    YOUR JOB: Verify that the extracted value ({original_value}) comes from the column with the SAME DURATION as the current period revenue ({current_revenue}).

    Common sense:
    - {original_value} should be a reasonable increase or decrease compared to {current_revenue} (usually within +/- 50%).
    - {original_value} should be in the same table as {current_revenue}.
    - {original_value} should be for three months or a quarter and NOT six months, nine months, or a full year.
    - {original_value} should come from the same row as {current_revenue}.

    If the value {original_value} is correct (correct period, correct duration), return it.
    If it is incorrect (wrong duration, e.g. YTD instead of Quarter), find the CORRECT value for {prior_label} with the matching duration.

    Return a JSON object:
    {{
        "verified_value": number (the correct value to use),
        "verified_unit": string (one of: "ones", "thousands", "millions", "billions"; use null if unknown. DO NOT use currency codes like RMB/USD),
        "correction_reason": "Explanation of why you changed it or kept it the same"
    }}

    Document Text:
    {{text[:30000]}}
    """

    try:
        formatted_prompt = reflection_prompt.replace("{text[:30000]}", text[:30000])
        result = call_llm_with_retry(formatted_prompt, temperature=0.0)

        verified_val = result.get("verified_value")
        verified_unit = result.get("verified_unit")
        correction_reason = result.get("correction_reason")

        if verified_val is not None:
            return float(verified_val), verified_unit, correction_reason

        # If LLM explicitly says it can't determine the value (verified_val is None),
        # but provides a reason (e.g. "duration mismatch"), we should return None to signal failure.
        if correction_reason:
            return None, None, correction_reason

        # Fallback to original if reflection returns nothing useful
        return original_value, original_unit, None
    except Exception as e:
        # Fallback on error
        # Raise error to prevent "green" pass-through of unverified data
        raise RuntimeError(f"Reflection failed: {e}") from e


def extract_prior_year_revenue(
    text: str,
    time_period: str,
    current_revenue: float | None = None,
    revenue_line_name: str | None = None,
    unit: str | None = None,
    period_end_date: str | None = None,
) -> tuple[float | None, str | None, str | None]:
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
            return (
                None,
                None,
                "Could not determine prior period label from time_period or period_end_date.",
            )

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
            return None, None, "LLM could not find prior year revenue explicitly."

        # Reflection step to ensure column duration consistency
        return _reflect_on_prior_revenue(
            revenue_value,
            revenue_unit,
            current_label,
            prior_label or time_period,
            current_revenue,
            text,  # Pass text to reflection
        )

    except Exception as e:
        # Re-raise to ensure the caller knows extraction failed critically
        raise RuntimeError(f"Prior year revenue extraction failed: {e}") from e


def extract_organic_growth_percentage_only(
    text: str, time_period: str, period_end_date: str | None = None
) -> float | None:
    """Step 1: Extract the organic growth percentage figure only."""
    from agents.extractor_utils import format_period_prompt_label

    period_info = format_period_prompt_label(time_period, period_end_date)
    prompt = f"""Analyze the provided document text for the {period_info}.
Your goal is to extract the "Constant Currency Organic Growth" percentage (or "Organic Growth" percentage) if it exists.

Instructions:
- Look for a numeric percentage explicitly labeled as "organic growth", "organic revenue growth", or "constant currency organic growth".
- Ignore simple revenue growth or other metrics.
- Return the raw number as a float (e.g., 5.5 for 5.5%, -2.3 for -2.3%).
- If not found, return null.

Document text:
{text[:30000]}

Return a JSON object:
{{
  "organic_growth_percentage": number or null
}}

Return only valid JSON."""

    try:
        response_text = generate_content_safe(prompt, temperature=0.0)
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        data = json.loads(response_text)
        return data.get("organic_growth_percentage")
    except Exception:
        return None


def reflect_on_organic_growth(
    text: str,
    organic_growth: float,
    simple_growth: float | None,
) -> dict:
    """Step 2: Reflect on the extracted value using the chunk and simple growth."""
    simple_growth_str = f"{simple_growth:.2f}%" if simple_growth is not None else "Unknown"
    organic_growth_str = f"{organic_growth}%"

    prompt = f"""You are a QA Auditor verifying data extraction.
You need to validate if the extracted "Organic Growth" figure makes sense in the context of the document and the calculated "Simple Growth".

Data:
- Extracted Organic Growth: {organic_growth_str}
- Calculated Simple Growth (Current vs Prior): {simple_growth_str}

Instructions:
1.  **Locate**: Confirm {organic_growth_str} appears in the text in the context of organic/constant currency growth.
2.  **Compare**:
    -   Does the text explain the difference (if any) between Simple Growth ({simple_growth_str}) and Organic Growth ({organic_growth_str})? (e.g. FX impact, M&A)
    -   If Simple Growth is 20% and Organic is 3%, are there major acquisitions mentioned?
    -   If the numbers are totally different with no explanation, the Organic Growth might be a hallucination or wrong number.
    -   If they are arguably consistent, ACCEPT the organic growth.
    -   If they contradict the text or common sense, REJECT it.

Document Text:
{text[:30000]}

Return a JSON object:
{{
  "is_valid": boolean,
  "reason": "Short explanation of your verification logic."
}}

Return only valid JSON."""

    try:
        response_text = generate_content_safe(prompt, temperature=0.0)
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        return json.loads(response_text)
    except Exception as e:
        return {"is_valid": False, "reason": f"Reflection failed: {e}"}


def extract_organic_growth(
    document_id: str,
    file_path: str,
    time_period: str,
    income_statement_data: dict,
    max_retries: int = 1,
) -> dict:
    # --- Step 1: Resolve Current and Prior Field Revenue & Calculate Simple Growth ---
    validation_errors: list[str] = []
    line_items = income_statement_data.get("line_items", [])
    current_unit = income_statement_data.get("unit")
    current_revenue = find_revenue_line_value(line_items)
    prior_revenue = income_statement_data.get("revenue_prior_year")
    prior_revenue_unit = None

    if prior_revenue is not None:
        prior_revenue_unit = current_unit  # Assume same if extracted together

    # If prior revenue is missing, try to extract it from the IS chunk
    if current_revenue is not None and prior_revenue is None:
        add_log(
            document_id,
            FinancialStatementMilestone.ORGANIC_GROWTH,
            "Prior period revenue missing from metadata. Attempting to extract from Income Statement context.",
        )
        is_chunk_index = income_statement_data.get("chunk_index")

        candidate_chunks_is = [is_chunk_index] if is_chunk_index is not None else []

        if candidate_chunks_is:
            is_text, _, _ = get_chunk_with_context(
                document_id, file_path, candidate_chunks_is[0], chars_before=2500, chars_after=2500
            )

            # Find line name for context
            revenue_line_name = None
            for item in line_items:
                if item.get("standardized_name") in ["total_revenue", "revenue"]:
                    revenue_line_name = item.get("line_name")
                    break

            # Extract
            extracted_prior_val, extracted_prior_unit, reason = extract_prior_year_revenue(
                is_text,
                time_period,
                current_revenue,
                revenue_line_name,
                current_unit,
                income_statement_data.get("period_end_date"),
            )

            if extracted_prior_val is not None:
                prior_revenue = extracted_prior_val
                prior_revenue_unit = extracted_prior_unit
                add_log(
                    document_id,
                    FinancialStatementMilestone.ORGANIC_GROWTH,
                    f"Resolved prior revenue: {prior_revenue} ({prior_revenue_unit}). Reason: {reason}",
                    source="gemini",
                )
            else:
                add_log(
                    document_id,
                    FinancialStatementMilestone.ORGANIC_GROWTH,
                    f"Could not resolve prior revenue. {reason}",
                    source="gemini",
                )

    if current_revenue is None:
        validation_errors.append("Current period revenue not found")
    if prior_revenue is None:
        validation_errors.append("Prior period revenue not found")

    # Calculate Simple Growth
    simple_growth = None
    if current_revenue is not None and prior_revenue is not None:
        # Normalize units
        current_rev_ones = convert_to_ones(float(current_revenue), current_unit)

        # Handle Prior Unit logic
        used_prior_unit = prior_revenue_unit
        if not used_prior_unit:
            used_prior_unit = current_unit
        else:
            # Sanity check unit
            # Check ratio
            ratio = (
                (float(current_revenue) / float(prior_revenue)) if float(prior_revenue) != 0 else 0
            )
            if 0.1 < ratio < 10:
                used_prior_unit = current_unit

        prior_rev_ones = convert_to_ones(float(prior_revenue), used_prior_unit)

        if prior_rev_ones != 0:
            simple_growth = (current_rev_ones - prior_rev_ones) / prior_rev_ones * 100
            prior_revenue_unit = used_prior_unit  # Update for return

    # --- Step 2: Find Chunk (constant currency organic growth) ---
    query_texts = ["constant currency organic growth", "constant currency", "organic growth"]

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

    # --- Step 3, 4, 5, 6: Extract, Format, Reflect, Confirm ---
    organic_growth = None

    if not text:
        validation_errors.append("Organic growth text section not found")
        add_log(
            document_id,
            FinancialStatementMilestone.ORGANIC_GROWTH,
            "Could not find section discussing constant currency organic growth.",
            source="system",
        )
    else:
        add_log(
            document_id,
            FinancialStatementMilestone.ORGANIC_GROWTH,
            "Found relevant section. Attempting to extract organic growth percentage.",
            source="system",
        )

        # Step 3 & 4: Extract and Post-process (handled by strict return type)
        extracted_val = extract_organic_growth_percentage_only(
            text, time_period, income_statement_data.get("period_end_date")
        )

        if extracted_val is not None:
            # Step 5: Reflect
            add_log(
                document_id,
                FinancialStatementMilestone.ORGANIC_GROWTH,
                f"Extracted candidate organic growth: {extracted_val}%. Reflecting against simple growth ({simple_growth if simple_growth is not None else 'N/A'}%) and text context.",
                source="system",
            )
            reflection = reflect_on_organic_growth(text, extracted_val, simple_growth)

            # Step 6: Confirm
            if reflection.get("is_valid"):
                organic_growth = extracted_val
                add_log(
                    document_id,
                    FinancialStatementMilestone.ORGANIC_GROWTH,
                    f"CONFIRMED Organic Growth: {organic_growth}%. Reason: {reflection.get('reason')}",
                    source="gemini",
                )
            else:
                add_log(
                    document_id,
                    FinancialStatementMilestone.ORGANIC_GROWTH,
                    f"REJECTED Organic Growth ({extracted_val}%). Reason: {reflection.get('reason')}. Fallback to simple growth.",
                    source="gemini",
                )
        else:
            add_log(
                document_id,
                FinancialStatementMilestone.ORGANIC_GROWTH,
                "Gemini could not explicitly extract an organic growth percentage from the text.",
                source="gemini",
            )

    # --- Step 6 (Fallback): If invalid/missing, usage simple growth ---
    final_organic_growth = organic_growth if (organic_growth is not None) else simple_growth

    is_valid_result = (
        not validation_errors and final_organic_growth is not None and current_revenue is not None
    )

    return {
        "currency": income_statement_data.get("currency"),
        "acquisition_flag": False,
        "acquisition_revenue_impact": None,
        "acquisition_revenue_impact_unit": None,
        "current_period_revenue": current_revenue,
        "current_period_revenue_unit": current_unit,
        "prior_period_revenue": prior_revenue,
        "prior_period_revenue_unit": prior_revenue_unit,
        "simple_revenue_growth": simple_growth,
        "current_period_adjusted_revenue": None,
        "current_period_adjusted_revenue_unit": current_unit,
        "organic_revenue_growth": final_organic_growth,
        "chunk_index": chunk_index,
        "is_valid": is_valid_result,
        "validation_errors": validation_errors,
    }
