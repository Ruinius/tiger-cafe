"""
GAAP/EBITDA reconciliation extraction agent for earnings announcements.
Uses chunk-based embedding search to find reconciliation tables, similar to balance sheet finding.
"""

from __future__ import annotations

import json
import re

from app.models.document import DocumentType
from app.utils.document_section_finder import find_document_section
from app.utils.financial_statement_progress import (
    FinancialStatementMilestone,
    add_log,
)
from app.utils.gemini_client import generate_content_safe


def find_gaap_ebitda_reconciliation_section(
    document_id: str,
    file_path: str,
    time_period: str,
    document_type: DocumentType | None = None,
    chunk_rank: int = 0,
    enable_logging: bool = True,
) -> tuple[str | None, int | None, dict | None]:
    """
    Use document embedding to locate the GAAP reconciliation or EBITDA reconciliation table.
    This is used specifically for earnings announcements.

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        time_period: Time period to search for (e.g., "Q3 2023")
        document_type: Document type (should be EARNINGS_ANNOUNCEMENT)
        chunk_rank: Rank of chunk to select (0 = best match, 1 = second best, etc.)
        enable_logging: Whether to add progress logs

    Returns:
        Tuple of (extracted_text, start_page, log_info) or (None, None, None) if not found
    """
    try:
        if enable_logging:
            rank_text = f" (rank {chunk_rank + 1})" if chunk_rank > 0 else ""
            section_msg = f"Finding GAAP/EBITDA reconciliation section{rank_text}"
            print(section_msg)
            add_log(
                document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, section_msg
            )
        # Determine ignore fractions based on document type
        doc_type_str = (
            document_type.value
            if hasattr(document_type, "value")
            else str(document_type)
            if document_type
            else None
        )

        if doc_type_str == "earnings_announcement":
            # For earnings announcements, ignore first 50% of chunks and look in second 50%
            ignore_front_fraction = 0.5
            ignore_back_fraction = 0.0
        else:
            # Default: ignore 10% from both edges
            ignore_front_fraction = 0.1
            ignore_back_fraction = 0.1

        # Initial query texts for finding GAAP/EBITDA reconciliation tables
        query_texts = [
            "GAAP reconciliation",
            "EBITDA reconciliation",
            "reconciliation of GAAP",
            "reconciliation of EBITDA",
            "non-GAAP reconciliation",
            "adjusted EBITDA",
        ]

        # Re-ranking query terms: common reconciliation table line items
        def normalize_term(term: str) -> str:
            # Lowercase, remove special characters except spaces, normalize whitespace
            normalized = term.lower()
            normalized = re.sub(r"[()]", "", normalized)  # Remove parentheses
            normalized = normalized.replace(",", "")  # Remove commas
            normalized = re.sub(r"\s+", " ", normalized)  # Normalize whitespace
            return normalized.strip()

        rerank_query_texts = [
            "amortization",
            "depreciation",
            "stock-based compensation",
            "acquisition-related",
            "restructuring",
            "non-GAAP",
            "adjusted",
            "reconciliation",
        ]
        rerank_query_texts = [normalize_term(term) for term in rerank_query_texts]

        result = find_document_section(
            document_id=document_id,
            file_path=file_path,
            query_texts=query_texts,
            chunk_size=None,
            score_threshold=0.3,
            pages_before=1,  # Include 1 page before the best chunk
            pages_after=1,  # Include 1 page after the best chunk
            rerank_top_k=5,
            rerank_query_texts=rerank_query_texts,
            ignore_front_fraction=ignore_front_fraction,
            ignore_back_fraction=ignore_back_fraction,
            chunk_rank=chunk_rank,
        )
        # Handle both old (2-tuple) and new (3-tuple) return formats for backward compatibility
        if len(result) == 2:
            text, start_page = result
            log_info = None
        else:
            text, start_page, log_info = result

        if enable_logging and text and log_info:
            rank_text = f" (rank {chunk_rank + 1})" if chunk_rank > 0 else ""
            chunk_msg = f"Best match{rank_text}: chunk {log_info.get('best_chunk_index')} (pages {log_info.get('chunk_start_page')}-{log_info.get('chunk_end_page')})"
            print(chunk_msg)
            add_log(document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, chunk_msg)

            pages_msg = f"Found GAAP/EBITDA reconciliation section (pages {log_info.get('start_extract_page')}-{log_info.get('end_extract_page')})"
            print(pages_msg)
            add_log(document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, pages_msg)

            found_msg = f"Found GAAP/EBITDA reconciliation section starting at page {start_page}, extracted {len(text)} characters"
            print(found_msg)
            add_log(document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, found_msg)
        elif enable_logging and not text:
            not_found_msg = f"GAAP/EBITDA reconciliation section not found (rank {chunk_rank + 1})"
            print(not_found_msg)
            add_log(
                document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, not_found_msg
            )

        if len(result) == 2:
            return result[0], result[1], None
        return result

    except Exception as e:
        error_msg = f"Error finding GAAP/EBITDA reconciliation section: {str(e)}"
        print(error_msg)
        if enable_logging:
            add_log(document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, error_msg)
        return None, None, None


def extract_gaap_reconciliation_llm(text: str, time_period: str) -> dict:
    """
    Extract line items from operating income or EBITDA reconciliation table.

    Args:
        text: Text containing GAAP reconciliation table
        time_period: Time period (e.g., "Q3 2024")

    Returns:
        Dictionary with extracted line items
    """
    prompt = f"""Extract all line items from the OPERATING INCOME reconciliation table or EBITDA reconciliation table
in the following document text for the time period: {time_period}.

IMPORTANT: Extract ONLY from operating income reconciliation or EBITDA reconciliation tables.
DO NOT extract from:
- Net income reconciliation tables
- Margin reconciliation tables
- EPS (earnings per share) reconciliation tables
- Any other type of reconciliation table

Focus on extracting all line items from the operating income or EBITDA reconciliation table, such as:
- Amortization
- Depreciation
- Stock-based compensation
- Acquisition-related expenses
- Restructuring charges
- Other adjustments that reconcile GAAP operating income or GAAP net income to non-GAAP operating income or EBITDA

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY extract values that are EXPLICITLY shown in the document text below
- DO NOT invent, infer, calculate, estimate, or approximate any values
- DO NOT create line items that do not appear in the document
- If a value is not visible in the document text, use null
- Extract line items ONLY from the operating income or EBITDA reconciliation table/section in the document text

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
- Non-operating examples: amortization of acquired intangibles, acquisition-related expenses, restructuring charges
- Operating examples: amortization of capitalized sales costs, amortization of capitalized software, stock-based compensation
- Default to operating unless explicitly financial, acquisition-related, or restructuring-related

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


def validate_reconciliation_table(line_items: list[dict]) -> tuple[bool, str]:
    """
    Validate that the sum of all line items except the last equals the last line item.

    Args:
        line_items: List of line items from reconciliation table

    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(line_items) < 2:
        return False, "Reconciliation table must have at least 2 line items"

    # Get all items except the last
    items_to_sum = line_items[:-1]
    last_item = line_items[-1]

    # Sum all values except the last
    total_sum = 0.0
    for item in items_to_sum:
        value = item.get("line_value")
        if value is not None:
            total_sum += float(value)

    # Get the last item's value
    last_value = last_item.get("line_value")
    if last_value is None:
        return False, "Last line item has no value"

    last_value_float = float(last_value)

    # Check if they match (allow small floating point differences)
    tolerance = 0.01
    if abs(total_sum - last_value_float) > tolerance:
        return (
            False,
            f"Sum of all items except last ({total_sum}) does not equal last item ({last_value_float}). Difference: {abs(total_sum - last_value_float)}",
        )

    return True, ""


def check_table_completeness(text: str, time_period: str) -> tuple[bool, str]:
    """
    Check if the chunk contains a complete GAAP to non-GAAP reconciliation table for EBITDA or operating income.

    Args:
        text: Text from chunk to check
        time_period: Time period (e.g., "Q3 2024")

    Returns:
        Tuple of (is_complete, explanation)
    """
    prompt = f"""Analyze the following document text for the time period: {time_period} and determine if it contains a COMPLETE GAAP to non-GAAP reconciliation table for either:
- EBITDA (Earnings Before Interest, Taxes, Depreciation, and Amortization)
- Operating Income

A complete reconciliation table should:
1. Start with a GAAP measure (GAAP operating income, GAAP net income, or similar)
2. List all adjustments/addbacks (amortization, depreciation, stock-based compensation, etc.)
3. End with the non-GAAP measure (non-GAAP operating income, EBITDA, adjusted EBITDA, etc.)
4. The sum of the starting GAAP measure plus all adjustments should equal the ending non-GAAP measure

IMPORTANT: The table must be for EBITDA or operating income reconciliation.
DO NOT consider:
- Net income reconciliation tables
- Margin reconciliation tables
- EPS (earnings per share) reconciliation tables
- Any other type of reconciliation table

Return a JSON object:
{{
  "is_complete": true or false,
  "explanation": "brief explanation of why it is or isn't complete"
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

    result = json.loads(response_text)
    return result.get("is_complete", False), result.get("explanation", "")


def check_completeness_and_extract(
    text: str, time_period: str, extracted_line_items: list[dict], validation_error: str
) -> dict:
    """
    Check if the reconciliation table is complete, and if not, extract a new correct one.

    Args:
        text: Text containing GAAP reconciliation table
        time_period: Time period (e.g., "Q3 2024")
        extracted_line_items: Previously extracted line items
        validation_error: Validation error message with numbers

    Returns:
        Dictionary with extracted line items or indication that table is incomplete
    """
    items_json = json.dumps(extracted_line_items, indent=2)
    prompt = f"""I extracted the following line items from what I thought was an operating income or EBITDA reconciliation table:

{items_json}

However, validation failed with this error:
{validation_error}

Please analyze the document text below and answer:
1. Do I have a COMPLETE operating income or EBITDA reconciliation table? (The sum of all items except the last should equal the last item)
2. If not, what line items am I missing?
3. If the table is incomplete, extract the complete and correct reconciliation table.

IMPORTANT: Extract ONLY from operating income reconciliation or EBITDA reconciliation tables.
DO NOT extract from:
- Net income reconciliation tables
- Margin reconciliation tables
- EPS (earnings per share) reconciliation tables
- Any other type of reconciliation table

If the table in the document is complete, return the same line items.
If the table is incomplete, extract ALL line items from the complete reconciliation table.

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY extract values that are EXPLICITLY shown in the document text below
- DO NOT invent, infer, calculate, estimate, or approximate any values
- DO NOT create line items that do not appear in the document
- If a value is not visible in the document text, use null

Return a JSON object with the following structure:
{{
  "is_complete": true or false,
  "missing_items": ["list of missing item names if incomplete"],
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

    response_text = generate_content_safe(prompt, temperature=0.0)
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
        response_text = response_text.strip()
    return json.loads(response_text)


def extract_gaap_reconciliation(
    document_id: str,
    file_path: str,
    time_period: str,
    document_type: DocumentType | None = None,
) -> dict:
    """
    Extract line items from operating income or EBITDA reconciliation table for earnings announcements.

    This extractor is exclusive to earnings announcements and uses chunk-based embedding search
    to find reconciliation tables, similar to the balance sheet finding workflow.

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        time_period: Time period (e.g., "Q3 2024")
        document_type: Document type (should be EARNINGS_ANNOUNCEMENT)

    Returns:
        Dictionary with extraction results:
        {
            "line_items": list of line items,
            "chunk_index": best chunk index found,
            "is_valid": bool,
            "validation_errors": list of error messages
        }
    """
    # Try chunks 0, 1, 2 in sequence to find a complete reconciliation table
    text = None
    chunk_index = None

    for rank in [0, 1, 2]:
        rank_text = f" (rank {rank + 1})" if rank > 0 else ""
        checking_msg = (
            f"Checking chunk{rank_text} for complete GAAP to non-GAAP reconciliation table"
        )
        print(checking_msg)
        add_log(document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, checking_msg)

        # Find the chunk
        chunk_text, chunk_start_page, chunk_log_info = find_gaap_ebitda_reconciliation_section(
            document_id=document_id,
            file_path=file_path,
            time_period=time_period,
            document_type=document_type,
            chunk_rank=rank,
            enable_logging=True,
        )

        if not chunk_text:
            not_found_msg = f"Chunk{rank_text} not found"
            print(not_found_msg)
            add_log(
                document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, not_found_msg
            )
            continue

        # Check if this chunk has a complete reconciliation table
        completeness_msg = f"Checking if chunk{rank_text} contains complete reconciliation table"
        print(completeness_msg)
        add_log(
            document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, completeness_msg
        )

        is_complete, explanation = check_table_completeness(chunk_text, time_period)

        if is_complete:
            complete_msg = f"Found complete reconciliation table in chunk{rank_text}: {explanation}"
            print(complete_msg)
            add_log(
                document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, complete_msg
            )
            text = chunk_text
            chunk_index = chunk_log_info.get("best_chunk_index") if chunk_log_info else None
            break
        else:
            incomplete_msg = (
                f"Chunk{rank_text} does not contain complete reconciliation table: {explanation}"
            )
            print(incomplete_msg)
            add_log(
                document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, incomplete_msg
            )

    if not text:
        error_msg = (
            "No complete GAAP to non-GAAP reconciliation table found after checking 3 chunks"
        )
        print(error_msg)
        add_log(document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, error_msg)
        return {
            "line_items": [],
            "chunk_index": None,
            "is_valid": False,
            "validation_errors": ["No complete GAAP to non-GAAP reconciliation table found"],
        }

    # Extract line items using LLM
    extraction_msg = "Extracting line items from operating income or EBITDA reconciliation table"
    print(extraction_msg)
    add_log(document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, extraction_msg)

    validation_errors: list[str] = []
    extraction = extract_gaap_reconciliation_llm(text, time_period)
    line_items = extraction.get("line_items", []) if isinstance(extraction, dict) else []

    extracted_count_msg = f"Extracted {len(line_items)} line items from reconciliation table"
    print(extracted_count_msg)
    add_log(
        document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, extracted_count_msg
    )

    # Validate: sum of all items except last should equal last item
    is_valid, validation_error = validate_reconciliation_table(line_items)

    if not is_valid and line_items:
        validation_errors.append(validation_error)
        validation_msg = f"Validation failed: {validation_error}"
        print(validation_msg)
        add_log(
            document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, validation_msg
        )

        # Check completeness and extract correct table if incomplete
        completeness_msg = (
            "Checking if reconciliation table is complete and extracting correct table if needed"
        )
        print(completeness_msg)
        add_log(
            document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, completeness_msg
        )

        completeness_result = check_completeness_and_extract(
            text, time_period, line_items, validation_error
        )

        # Use the extracted line items from completeness check (whether complete or not)
        new_line_items = completeness_result.get("line_items", [])

        if completeness_result.get("is_complete", False):
            # LLM determined table is complete, use the corrected extraction
            line_items = new_line_items
            corrected_msg = (
                f"Table is complete. Using corrected extraction with {len(line_items)} line items"
            )
            print(corrected_msg)
            add_log(
                document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, corrected_msg
            )
        else:
            # Table was incomplete, use the new extraction
            missing_items = completeness_result.get("missing_items", [])
            if missing_items:
                missing_msg = f"Table was incomplete. Missing items: {', '.join(missing_items)}"
                print(missing_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                    missing_msg,
                )

            line_items = new_line_items
            if line_items:
                corrected_msg = f"Extracted complete table with {len(line_items)} line items"
                print(corrected_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
                    corrected_msg,
                )

        # Re-validate the new/corrected extraction
        if line_items:
            is_valid, validation_error = validate_reconciliation_table(line_items)
            if not is_valid:
                validation_errors.append(
                    f"Validation failed after completeness check: {validation_error}"
                )
            else:
                validation_errors = []  # Clear errors if validation now passes

    if not line_items:
        validation_errors.append("No reconciliation line items extracted")
        error_msg = "No reconciliation line items extracted"
        print(error_msg)
        add_log(document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, error_msg)
        is_valid = False
    elif is_valid:
        success_msg = f"Non-GAAP reconciliation extraction completed: {len(line_items)} line items"
        print(success_msg)
        add_log(document_id, FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS, success_msg)

    return {
        "line_items": line_items,
        "chunk_index": chunk_index,
        "is_valid": is_valid,
        "validation_errors": validation_errors,
    }
