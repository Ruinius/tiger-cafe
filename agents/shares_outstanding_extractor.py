"""
Shares outstanding extraction agent using Gemini LLM and embeddings
"""

from __future__ import annotations

import json

from app.utils.document_section_finder import find_document_section
from app.utils.financial_statement_progress import (
    FinancialStatementMilestone,
    add_log,
)
from app.utils.gemini_client import generate_content_safe


def extract_shares_outstanding_llm(
    text: str, time_period: str, period_end_date: str | None = None
) -> dict:
    from agents.extractor_utils import format_period_prompt_label

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
  "diluted_shares_outstanding_unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (null if not stated)
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
) -> dict:
    query_texts = ["weighted average", "shares", "basic", "diluted"]

    # Try ranks 0, 1, 2 in sequence (top 3 ranking chunks)
    # Each attempt uses 1 chunk with 2500 chars before and 2500 chars after
    for rank in [0, 1, 2]:
        text, chunk_index, log_info = find_document_section(
            document_id=document_id,
            file_path=file_path,
            query_texts=query_texts,
            chars_before=2500,
            chars_after=2500,
            rerank_top_k=3,
            score_threshold=0.25,
            chunk_rank=rank,
            context_name="Shares Outstanding",
        )

        add_log(
            document_id,
            FinancialStatementMilestone.SHARES_OUTSTANDING,
            f"I'm searching for basic and diluted shares outstanding figures (attempt {rank + 1}).",
        )

        if not text:
            continue

        # Try extraction from this chunk
        add_log(
            document_id,
            FinancialStatementMilestone.SHARES_OUTSTANDING,
            f"I'm asking Gemini to find the weighted average shares (basic and diluted) for {time_period}.",
        )
        extraction = extract_shares_outstanding_llm(text, time_period, period_end_date)
        if extraction.get("basic_shares_outstanding") or extraction.get(
            "diluted_shares_outstanding"
        ):
            add_log(
                document_id,
                FinancialStatementMilestone.SHARES_OUTSTANDING,
                f"Gemini response: Shares found. Basic: {extraction.get('basic_shares_outstanding')} {extraction.get('basic_shares_outstanding_unit', '')}, Diluted: {extraction.get('diluted_shares_outstanding')} {extraction.get('diluted_shares_outstanding_unit', '')}.",
                source="gemini",
            )
        else:
            add_log(
                document_id,
                FinancialStatementMilestone.SHARES_OUTSTANDING,
                "Gemini response: No clear share counts identified in this document segment.",
                source="gemini",
            )
        retries = 0
        while retries < max_retries and not extraction:
            retries += 1
            extraction = extract_shares_outstanding_llm(text, time_period, period_end_date)

        is_valid = any(
            extraction.get(field) is not None
            for field in ("basic_shares_outstanding", "diluted_shares_outstanding")
        )

        if is_valid:
            return {
                "basic_shares_outstanding": extraction.get("basic_shares_outstanding"),
                "basic_shares_outstanding_unit": extraction.get("basic_shares_outstanding_unit"),
                "diluted_shares_outstanding": extraction.get("diluted_shares_outstanding"),
                "diluted_shares_outstanding_unit": extraction.get(
                    "diluted_shares_outstanding_unit"
                ),
                "chunk_index": chunk_index,
                "is_valid": is_valid,
                "validation_errors": [],
            }

    # If all attempts failed, return error
    return {
        "basic_shares_outstanding": None,
        "basic_shares_outstanding_unit": None,
        "diluted_shares_outstanding": None,
        "diluted_shares_outstanding_unit": None,
        "chunk_index": None,
        "is_valid": False,
        "validation_errors": ["Shares outstanding section not found"],
    }
