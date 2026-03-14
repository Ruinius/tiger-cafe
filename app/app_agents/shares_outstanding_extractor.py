"""
Shares outstanding extraction agent using Gemini LLM
"""

from __future__ import annotations

import json

from app.utils.document_section_finder import extract_context_around_keywords
from app.utils.financial_statement_progress import (
    FinancialStatementMilestone,
    add_log,
)
from app.utils.gemini_client import generate_content_safe


def extract_shares_outstanding_llm(
    text: str, time_period: str, period_end_date: str | None = None
) -> dict:
    from app.app_agents.extractor_utils import format_period_prompt_label

    period_info = format_period_prompt_label(time_period, period_end_date)
    prompt = f"""Extract basic and diluted shares outstanding from the following document text for the {period_info}.

IMPORTANT GUIDANCE ON LABELING:
- Basic and diluted shares outstanding may not be explicitly labeled as "basic shares outstanding" or "diluted shares outstanding"
- Look for alternative labels such as:
  - "shares used to calculate basic EPS" or "basic EPS shares"
  - "shares used to calculate diluted EPS" or "diluted EPS shares"
  - "weighted average basic shares" or "weighted average diluted shares"
  - "basic weighted average shares" or "diluted weighted average shares"
  - Any table or section that shows share counts used for EPS calculations
- The values may appear in EPS (earnings per share) calculation tables or footnotes

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY extract values that are EXPLICITLY shown in the document text below
- DO NOT invent, infer, calculate, estimate, or approximate any values
- If a value is not visible, use null

Return a JSON object:
{{
  "basic_shares_outstanding": number (null if not found),
  "basic_shares_outstanding_unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (null if not stated),
  "diluted_shares_outstanding": number (null if not found),
  "diluted_shares_outstanding_unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (null if not stated),
  "not_found_reason": "brief explanation if specific values are missing or if the section is irrelevant"
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


def extract_shares_outstanding(
    document_id: str,
    file_path: str,
    time_period: str,
    max_retries: int = 1,
    period_end_date: str | None = None,
    income_statement_chunk_index: int | None = None,
) -> dict:
    from app.utils.document_indexer import load_full_document_text
    from app.utils.document_section_finder import get_chunk_with_context

    # --- ATTEMPT 1: Check Income Statement Chunk (if available) ---
    if income_statement_chunk_index is not None:
        add_log(
            document_id,
            FinancialStatementMilestone.SHARES_OUTSTANDING,
            "Checking Income Statement section for shares data...",
        )
        # Use generous context as EPS is often at the bottom of the IS
        text, _, _ = get_chunk_with_context(
            document_id=document_id,
            file_path=file_path,
            chunk_index=income_statement_chunk_index,
            chars_before=2500,
            chars_after=2500,
        )

        if text:
            # Try extraction on the raw IS chunk text
            extraction = extract_shares_outstanding_llm(text, time_period, period_end_date)

            is_valid = any(
                extraction.get(field) is not None
                for field in ("basic_shares_outstanding", "diluted_shares_outstanding")
            )

            if is_valid:
                add_log(
                    document_id,
                    FinancialStatementMilestone.SHARES_OUTSTANDING,
                    f"Found shares in Income Statement chunk (Basic: {extraction.get('basic_shares_outstanding')}, Diluted: {extraction.get('diluted_shares_outstanding')})",
                )
                return {
                    "basic_shares_outstanding": extraction.get("basic_shares_outstanding"),
                    "basic_shares_outstanding_unit": extraction.get(
                        "basic_shares_outstanding_unit"
                    ),
                    "diluted_shares_outstanding": extraction.get("diluted_shares_outstanding"),
                    "diluted_shares_outstanding_unit": extraction.get(
                        "diluted_shares_outstanding_unit"
                    ),
                    "chunk_index": income_statement_chunk_index,
                    "is_valid": True,
                    "validation_errors": [],
                }
            else:
                if extraction.get("not_found_reason"):
                    add_log(
                        document_id,
                        FinancialStatementMilestone.SHARES_OUTSTANDING,
                        f"Gemini response: {extraction.get('not_found_reason')}",
                        source="gemini",
                    )
                add_log(
                    document_id,
                    FinancialStatementMilestone.SHARES_OUTSTANDING,
                    "Shares not found in Income Statement chunk. Proceeding to global search.",
                )

    # --- ATTEMPT 2: Global Keyword Search ---
    add_log(
        document_id,
        FinancialStatementMilestone.SHARES_OUTSTANDING,
        "Scanning entire document for shares-related keywords...",
    )

    full_text = load_full_document_text(document_id, file_path)
    if not full_text:
        return {
            "basic_shares_outstanding": None,
            "basic_shares_outstanding_unit": None,
            "diluted_shares_outstanding": None,
            "diluted_shares_outstanding_unit": None,
            "chunk_index": None,
            "is_valid": False,
            "validation_errors": ["Could not load document text"],
        }

    keywords = ["weighted average", "shares outstanding", "basic", "diluted"]
    # Get all relevant snippets from the document
    focused_text = extract_context_around_keywords(full_text, keywords, context_chars=250)

    if not focused_text:
        return {
            "basic_shares_outstanding": None,
            "basic_shares_outstanding_unit": None,
            "diluted_shares_outstanding": None,
            "diluted_shares_outstanding_unit": None,
            "chunk_index": None,
            "is_valid": False,
            "validation_errors": ["No shares-related keywords found in document"],
        }

    # Split focused text into regular chunks to avoid context window issues
    snippet_size = 2500
    snippets = [
        focused_text[i : i + snippet_size] for i in range(0, len(focused_text), snippet_size)
    ]

    add_log(
        document_id,
        FinancialStatementMilestone.SHARES_OUTSTANDING,
        f"Found relevant text segments. Analyzing {len(snippets)} snippets...",
    )

    for i, snippet in enumerate(snippets):
        extraction = extract_shares_outstanding_llm(snippet, time_period, period_end_date)

        is_valid = any(
            extraction.get(field) is not None
            for field in ("basic_shares_outstanding", "diluted_shares_outstanding")
        )

        if is_valid:
            add_log(
                document_id,
                FinancialStatementMilestone.SHARES_OUTSTANDING,
                f"Found shares in keyword snippet {i + 1} (Basic: {extraction.get('basic_shares_outstanding')}, Diluted: {extraction.get('diluted_shares_outstanding')})",
            )
            return {
                "basic_shares_outstanding": extraction.get("basic_shares_outstanding"),
                "basic_shares_outstanding_unit": extraction.get("basic_shares_outstanding_unit"),
                "diluted_shares_outstanding": extraction.get("diluted_shares_outstanding"),
                "diluted_shares_outstanding_unit": extraction.get(
                    "diluted_shares_outstanding_unit"
                ),
                "chunk_index": None,  # Chunk index is ambiguous for keyword search results
                "is_valid": True,
                "validation_errors": [],
            }
        else:
            if extraction.get("not_found_reason"):
                add_log(
                    document_id,
                    FinancialStatementMilestone.SHARES_OUTSTANDING,
                    f"Gemini response (snippet {i + 1}): {extraction.get('not_found_reason')}",
                    source="gemini",
                )

    # Final Failure
    add_log(
        document_id,
        FinancialStatementMilestone.SHARES_OUTSTANDING,
        "Failed to extract shares outstanding from any section.",
    )
    return {
        "basic_shares_outstanding": None,
        "basic_shares_outstanding_unit": None,
        "diluted_shares_outstanding": None,
        "diluted_shares_outstanding_unit": None,
        "chunk_index": None,
        "is_valid": False,
        "validation_errors": ["Shares outstanding not found in document"],
    }
