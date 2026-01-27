import json
import time  # Added import for time.sleep
from typing import Any

from app.utils.gemini_client import generate_content_safe


def clean_json_response(response_text: str) -> str:
    """Removes markdown code blocks from LLM response."""
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
        response_text = response_text.strip()
    elif "```" in response_text:
        # Handle case where it's wrapped in backticks but not at the very start (e.g. whitespace)
        # or just backticks without language identifier
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
        response_text = response_text.strip()
    return response_text


def call_llm_and_parse_json(prompt: str, temperature: float = 0.0) -> dict[str, Any]:
    """Calls LLM and parses the JSON response."""
    try:
        response_text = generate_content_safe(prompt, temperature=temperature)
        cleaned_text = clean_json_response(response_text)
        return json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse LLM response as JSON: {str(e)}")
    except Exception as e:
        raise Exception(f"LLM call failed: {str(e)}")


def call_llm_with_retry(
    prompt: str, max_retries: int = 3, temperature: float = 0.0
) -> dict[str, Any]:
    """Calls LLM with retry logic for API errors."""
    for attempt in range(max_retries):
        try:
            return call_llm_and_parse_json(prompt, temperature)
        except Exception as e:
            error_str = str(e).lower()
            is_api_error = any(
                keyword in error_str
                for keyword in [
                    "rate limit",
                    "quota",
                    "429",
                    "500",
                    "503",
                    "internal",
                    "resource exhausted",
                    "service unavailable",
                    "too many requests",
                    "json",
                    "decode",
                ]
            )

            # Retry on JSON errors too
            if isinstance(e, json.JSONDecodeError):
                is_api_error = True

            if is_api_error and attempt < max_retries - 1:
                wait_time = 2**attempt
                time.sleep(wait_time)
                continue

            if attempt == max_retries - 1:
                raise e
    raise Exception("Should not reach here")


def check_section_completeness_llm(
    text: str,
    time_period: str,
    statement_name: str,
    validation_criteria: str,
    period_end_date: str | None = None,
) -> tuple[bool, str]:
    """
    Generic function to check if a document section contains a complete financial statement.
    """
    period_info = f"time period in fiscal: {time_period}"
    if period_end_date:
        period_info += f" (period ending in calendar {period_end_date})"

    prompt = f"""Analyze the following document text to determine if it contains a COMPLETE {statement_name} for the {period_info}.

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY use information from the provided document text below
- DO NOT use external knowledge or assumptions
- Base your assessment ONLY on what is provided in the text

A COMPLETE {statement_name} should:
{validation_criteria}
- Avoid smaller informational tables that do not have the complete information

Document text:
{text}

Return a JSON object:
{{
    "is_complete": true or false,
    "reason": "brief explanation of why it is or is not complete (only if not complete)"
}}

Return only valid JSON, no additional text."""

    try:
        result = call_llm_with_retry(prompt)
        return result.get("is_complete", False), result.get("reason", "")
    except Exception as e:
        return False, str(e)


def get_llm_insights_generic(
    line_items: list[dict[str, Any]],
    statement_type_description: str,
    json_structure_description: str,
    guidance_text: str,
) -> tuple[dict[str, Any], list[str]]:
    """
    Generic function to identify key line items in a financial statement.
    """
    if not line_items:
        return {}, []

    line_items_text = "\n".join(
        [
            f"{idx + 1}. {item['line_name']} | {item['line_value']}"
            for idx, item in enumerate(line_items)
        ]
    )

    prompt = f"""You are analyzing {statement_type_description}. Identify key line items by name.
Return ONLY valid JSON using the exact line names provided.

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY match line items that ACTUALLY appear in the provided line items list below
- DO NOT invent line names - use null if a line item is not found in the list
- Match line names exactly as they appear in the list (case-sensitive matching is preferred)

Line items:
{line_items_text}

Return this JSON structure:
{json_structure_description}

Guidance for matching (but only use names that actually appear in the list above):
{guidance_text}

Return only JSON with no extra text."""

    try:
        insights = call_llm_and_parse_json(prompt)
        return insights, []
    except Exception as exc:
        return {}, [f"LLM insights unavailable: {str(exc)}"]
