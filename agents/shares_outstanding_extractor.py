"""
Shares outstanding extraction agent using Gemini LLM and embeddings
"""

from __future__ import annotations

import json

from app.utils.document_section_helpers import collect_top_chunk_texts
from app.utils.gemini_client import generate_content_safe


def extract_shares_outstanding_llm(text: str, time_period: str) -> dict:
    prompt = f"""Extract basic and diluted shares outstanding from the following document text for the time period: {time_period}.

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
) -> dict:
    query_texts = ["weighted average", "shares", "basic", "diluted"]
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
            "basic_shares_outstanding": None,
            "basic_shares_outstanding_unit": None,
            "diluted_shares_outstanding": None,
            "diluted_shares_outstanding_unit": None,
            "chunk_index": None,
            "is_valid": False,
            "validation_errors": ["Shares outstanding section not found"],
        }

    extraction = extract_shares_outstanding_llm(text, time_period)
    retries = 0
    while retries < max_retries and not extraction:
        retries += 1
        extraction = extract_shares_outstanding_llm(text, time_period)

    is_valid = any(
        extraction.get(field) is not None
        for field in ("basic_shares_outstanding", "diluted_shares_outstanding")
    )

    validation_errors = []
    if not is_valid:
        validation_errors.append("No shares outstanding values extracted")

    return {
        "basic_shares_outstanding": extraction.get("basic_shares_outstanding"),
        "basic_shares_outstanding_unit": extraction.get("basic_shares_outstanding_unit"),
        "diluted_shares_outstanding": extraction.get("diluted_shares_outstanding"),
        "diluted_shares_outstanding_unit": extraction.get("diluted_shares_outstanding_unit"),
        "chunk_index": chunk_index,
        "is_valid": is_valid,
        "validation_errors": validation_errors,
    }
