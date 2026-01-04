"""
Balance sheet extraction agent using Gemini LLM and embeddings
"""

import json
import re

from app.utils.document_section_finder import find_document_section
from app.utils.financial_statement_progress import (
    FinancialStatementMilestone,
    add_log,
)
from app.utils.gemini_client import generate_content_safe
from app.utils.pdf_extractor import extract_text_from_pdf


def find_balance_sheet_section(
    document_id: str, file_path: str, time_period: str
) -> tuple[str | None, int | None, dict | None]:
    """
    Use document embedding to locate the consolidated balance sheet section.

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        time_period: Time period to search for (e.g., "Q3 2023")

    Returns:
        Tuple of (extracted_text, start_page, log_info) or (None, None, None) if not found
    """
    try:
        # Generate query embeddings for various balance sheet names
        query_texts = [
            "consolidated balance sheet",
            "balance sheet",
            "total assets",
            "total liabilities",
        ]
        result = find_document_section(
            document_id=document_id,
            file_path=file_path,
            query_texts=query_texts,
            chunk_size=None,
            score_threshold=0.3,
            pages_before=1,  # Include 1 page before the best chunk
            pages_after=1,  # Include 1 page after the best chunk
        )
        # Handle both old (2-tuple) and new (3-tuple) return formats for backward compatibility
        if len(result) == 2:
            return result[0], result[1], None
        return result

    except Exception as e:
        print(f"Error finding balance sheet section: {str(e)}")
        return None, None, None


def extract_balance_sheet_llm(text: str, time_period: str, currency: str | None = None) -> dict:
    """
    Use LLM to extract balance sheet line items exactly line by line.

    Args:
        text: Text containing balance sheet
        time_period: Time period (e.g., "Q3 2023")
        currency: Currency code if known

    Returns:
        Dictionary with balance sheet data
    """
    prompt = f"""Extract the balance sheet from the following document text for the time period: {time_period}.
Extract the balance sheet exactly line by line, including all line items and their values.
If the company is foreign, extract the values in the local currency.

Return a JSON object with the following structure:
{{
    "currency": currency code (extract from document),
    "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (extract from document, e.g., if values are in millions, use "millions"),
    "time_period": "{time_period}",
    "line_items": [
        {{
            "line_name": "exact name as it appears in the document but do not include long notes in parentheses",
            "line_value": numeric value (as number, not string),
            "line_category": one of ["Current Assets", "Non-Current Assets", "Total Assets", "Current Liabilities", "Non-Current Liabilities", "Total Liabilities", "Equity", "Total Liabilities and Equity"]
        }},
        ...
    ]
}}

IMPORTANT:
- Extract values exactly as they appear (including negative values if present)
- Include all subtotals (Current Assets, Total Assets, Current Liabilities, Total Liabilities, Total Equity, Total Liabilities and Equity)
- Maintain the exact order of line items as they appear in the document
- Extract the currency code from the document if available
- Extract the unit from the document (look for notes like "in millions", "in thousands", "in billions", or "in ten thousands" for foreign stocks)
- Values should be numeric (not strings with commas or currency symbols)
- Use "ten_thousands" only if the stock is foreign and the document explicitly states values are in ten thousands

Document text:
{text[:30000]}  # Limit to 30k characters

Return only valid JSON, no additional text."""

    try:
        response_text = generate_content_safe(prompt)

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        result = json.loads(response_text)

        # Ensure line_items exists and is a list
        if "line_items" not in result:
            result["line_items"] = []
        elif not isinstance(result["line_items"], list):
            result["line_items"] = []

        return result

    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse LLM response as JSON: {str(e)}")
    except Exception as e:
        raise Exception(f"Error extracting balance sheet: {str(e)}")


def validate_balance_sheet(line_items: list[dict]) -> tuple[bool, list[str]]:
    """
    Validate balance sheet calculations.

    Args:
        line_items: List of balance sheet line items

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check if line_items is empty
    if not line_items or len(line_items) == 0:
        errors.append("Balance sheet is empty - no line items extracted")
        return False, errors

    # Check if we have at least some meaningful line items (not just empty strings)
    valid_items = [
        item for item in line_items if item.get("line_name") and item.get("line_name").strip()
    ]
    if len(valid_items) == 0:
        errors.append("Balance sheet has no valid line items")
        return False, errors

    # Convert to dictionary for easier lookup
    items_dict = {item["line_name"].lower(): item["line_value"] for item in line_items}

    # Find key totals
    current_assets = None
    total_assets = None
    current_liabilities = None
    total_liabilities = None
    total_equity = None
    total_liabilities_equity = None

    # Helper function to check if a line name is a total line
    # More precise: checks if "total" appears as a distinct word at the start or as part of a total phrase
    def is_total_line_name(name_lower):
        """Check if line name represents a total (more precise matching)"""
        # Check for exact total phrases at the start of the name
        total_phrases = [
            "total current assets",
            "total assets",
            "total current liabilities",
            "total liabilities",
            "total equity",
            "total liabilities and equity",
            "total liabilities and shareholders",
            "total stockholder",
            "total shareholder",
        ]
        # Check if name starts with any total phrase
        for phrase in total_phrases:
            if name_lower.startswith(phrase) or name_lower.startswith(phrase + " "):
                return True
        # Also check if "total" appears as a distinct word (not part of another word)
        # Match "total" as a whole word (not part of "totally", "totaled", etc.)
        if re.search(r"\btotal\b", name_lower):
            # But exclude if it's clearly not a total line (e.g., "accounts receivable, net (total...")
            # Only consider it a total if "total" appears near the start or with key financial terms
            if (
                name_lower.startswith("total ")
                or "total current" in name_lower
                or "total assets" in name_lower
                or "total liabilities" in name_lower
                or "total equity" in name_lower
            ):
                return True
        return False

    for key, value in items_dict.items():
        # Use more precise matching for totals
        if is_total_line_name(key):
            # Check for "total current assets" - must contain both "total" and "current assets", but NOT "non-current"
            if (
                "current assets" in key
                and "non-current" not in key
                and "total non-current assets" not in key
            ):
                current_assets = value
            # Check for "total assets" - must contain "total assets" but NOT "non-current", "current", or "liabilities"
            elif (
                "total assets" in key
                and "non-current" not in key
                and "current" not in key
                and "liabilities" not in key
                and "total non-current assets" not in key
            ):
                total_assets = value
            # Check for "total current liabilities" - must contain both "total" and "current liabilities", but NOT "non-current"
            elif (
                "current liabilities" in key
                and "non-current" not in key
                and "total non-current liabilities" not in key
            ):
                current_liabilities = value
            # Check for "total liabilities" - must contain "total liabilities" but NOT "non-current", "current", or "equity"
            elif (
                "total liabilities" in key
                and "non-current" not in key
                and "current" not in key
                and "equity" not in key
                and "total non-current liabilities" not in key
            ):
                total_liabilities = value
            # Check for "total equity" - must contain "total equity" but NOT "liabilities"
            elif "total equity" in key and "liabilities" not in key:
                total_equity = value
            # Check for "total liabilities and equity" or "total liabilities and shareholders"
            elif (
                "total liabilities and equity" in key or "total liabilities and shareholders" in key
            ):
                total_liabilities_equity = value

    # Calculate sums from line items
    # Only sum base line items, exclude any totals or subtotals
    # Exclude items that are totals themselves (by name or category)
    def is_total_item(item):
        """Check if an item is a total/subtotal line (more precise)"""
        name_lower = item["line_name"].lower()
        category = item.get("line_category", "")

        # Use the same precise matching function
        if is_total_line_name(name_lower):
            return True

        # Also check category
        if "Total" in category:
            return True

        # Check for other total indicators (subtotal, sum) as whole words
        if re.search(r"\bsubtotal\b", name_lower) or re.search(r"\bsum\b", name_lower):
            return True

        return False

    # Only include base line items (not totals) in the EXACT correct category
    # Be very explicit about category matching to avoid confusion
    current_assets_sum = sum(
        item["line_value"]
        for item in line_items
        if (
            item.get("line_category", "").strip() == "Current Assets"
            and not is_total_item(item)
            and "non-current" not in item.get("line_name", "").lower()
        )
    )

    total_assets_sum = sum(
        item["line_value"]
        for item in line_items
        if (
            item.get("line_category", "").strip() in ["Current Assets", "Non-Current Assets"]
            and not is_total_item(item)
        )
    )

    current_liabilities_sum = sum(
        item["line_value"]
        for item in line_items
        if (
            item.get("line_category", "").strip() == "Current Liabilities"
            and not is_total_item(item)
            and "non-current" not in item.get("line_name", "").lower()
        )
    )

    total_liabilities_sum = sum(
        item["line_value"]
        for item in line_items
        if (
            item.get("line_category", "").strip()
            in ["Current Liabilities", "Non-Current Liabilities"]
            and not is_total_item(item)
        )
    )

    # Validate current assets
    if current_assets is not None:
        diff = abs(current_assets - current_assets_sum)
        if diff > 0.01:  # Allow small rounding differences
            errors.append(
                f"Current assets sum mismatch: reported={current_assets}, calculated={current_assets_sum}"
            )

    # Validate total assets
    if total_assets is not None:
        diff = abs(total_assets - total_assets_sum)
        if diff > 0.01:
            errors.append(
                f"Total assets sum mismatch: reported={total_assets}, calculated={total_assets_sum}"
            )

    # Validate current liabilities
    if current_liabilities is not None:
        diff = abs(current_liabilities - current_liabilities_sum)
        if diff > 0.01:
            errors.append(
                f"Current liabilities sum mismatch: reported={current_liabilities}, calculated={current_liabilities_sum}"
            )

    # Validate total liabilities
    if total_liabilities is not None:
        diff = abs(total_liabilities - total_liabilities_sum)
        if diff > 0.01:
            errors.append(
                f"Total liabilities sum mismatch: reported={total_liabilities}, calculated={total_liabilities_sum}"
            )

    # Validate balance sheet equation: Assets = Liabilities + Equity
    if total_assets is not None and total_liabilities is not None and total_equity is not None:
        liabilities_equity_sum = total_liabilities + total_equity
        diff = abs(total_assets - liabilities_equity_sum)
        if diff > 0.01:
            errors.append(
                f"Balance sheet equation mismatch: Assets={total_assets}, Liabilities+Equity={liabilities_equity_sum}"
            )

    # Validate total liabilities and equity
    if total_liabilities_equity is not None and total_assets is not None:
        diff = abs(total_assets - total_liabilities_equity)
        if diff > 0.01:
            errors.append(
                f"Total liabilities and equity mismatch: reported={total_liabilities_equity}, should equal total assets={total_assets}"
            )

    # Check if we have at least one key total (total assets, total liabilities, or total equity)
    # This ensures we didn't get an empty or invalid balance sheet
    if total_assets is None and total_liabilities is None and total_equity is None:
        errors.append(
            "Balance sheet is missing key totals (Total Assets, Total Liabilities, or Total Equity)"
        )

    return len(errors) == 0, errors


def normalize_line_name(name: str) -> str:
    """
    Normalize a line item name for matching: trim, case-insensitive,
    collapse whitespace, remove leading/trailing punctuation.
    """
    if not name:
        return ""
    # Trim
    normalized = name.strip()
    # Case-insensitive (convert to lowercase)
    normalized = normalized.lower()
    # Collapse repeated whitespace
    normalized = re.sub(r"\s+", " ", normalized)
    # Remove leading/trailing punctuation
    normalized = normalized.strip(".,;:!?()[]{}")
    return normalized


def classify_line_items_llm(line_items: list[dict]) -> list[dict]:
    """
    Use LLM to categorize each balance sheet line item as operating or non-operating.

    Args:
        line_items: List of balance sheet line items

    Returns:
        List of line items with is_operating field added
    """
    # AUTHORITATIVE_LOOKUP - binding decision table
    AUTHORITATIVE_LOOKUP = {
        "Cash and cash equivalents": "Non-Operating",
        "Marketable securities / Short-term investments": "Non-Operating",
        "Restricted cash": "Non-Operating",
        "Accounts receivable": "Operating",
        "Notes receivable (trade-related)": "Operating",
        "Inventories": "Operating",
        "Prepaid expenses": "Operating",
        "Other current assets": "Operating",
        "Property, plant and equipment (PPE)": "Operating",
        "Operating lease right-of-use assets": "Non-Operating",
        "Goodwill": "Non-Operating",
        "Intangible assets": "Non-Operating",
        "Long-term investments / Equity method investments": "Non-Operating",
        "Deferred tax assets": "Operating",
        "Other non-current assets": "Operating",
        "Accounts payable": "Operating",
        "Accrued expenses / Accrued liabilities": "Operating",
        "Unearned revenue / Deferred revenue": "Operating",
        "Short-term debt": "Non-Operating",
        "Current portion of long-term debt": "Non-Operating",
        "Current lease liabilities": "Non-Operating",
        "Other current liabilities": "Operating",
        "Long-term debt": "Non-Operating",
        "Non-current lease liabilities": "Non-Operating",
        "Deferred tax liabilities": "Operating",
        "Pension liabilities / Postretirement obligations": "Operating",
        "Other long-term liabilities": "Operating",
        "Common stock / Paid-in capital": "Non-Operating",
        "Retained earnings": "Non-Operating",
        "Treasury stock": "Non-Operating",
        "Accumulated other comprehensive income (AOCI)": "Non-Operating",
        "Noncontrolling interests": "Non-Operating",
        "Deferred compensation / Stock-based compensation liability": "Operating",
        "Customer deposits": "Operating",
        "Contract liabilities": "Operating",
        "Income taxes payable": "Operating",
        "Accrued payroll / Accrued compensation": "Operating",
        "Derivative assets/liabilities": "Non-Operating",
    }

    # Create normalized lookup map
    normalized_lookup = {normalize_line_name(k): v for k, v in AUTHORITATIVE_LOOKUP.items()}

    # Prepare lookup context for prompt
    lookup_context = "\n".join([f'  "{k}": "{v}"' for k, v in AUTHORITATIVE_LOOKUP.items()])

    prompt = f"""Classify each balance sheet line item as either "operating" or "non-operating" based on whether it relates to the company's core business operations.

HIGHEST PRIORITY: Use the AUTHORITATIVE_LOOKUP below as a binding decision table.
- If a provided line item matches a key in AUTHORITATIVE_LOOKUP after normalization, you MUST use that value.
- Normalization: trim, case-insensitive, collapse repeated whitespace, remove leading/trailing punctuation.
- If no match: use the fallback heuristics.
- If still uncertain: use best judgement.

FALLBACK HEURISTICS (only when no lookup match):
- Cash, marketable securities, debt, equity, goodwill, intangibles, lease ROU assets/liabilities -> Non-Operating
- Working capital items (AR, inventory, AP, accrued op expenses), PPE -> Operating
- Deferred taxes -> Operating (unless clearly financing-related)
- If mixed/ambiguous -> Unknown

AUTHORITATIVE_LOOKUP:
{{
{lookup_context}
}}

Balance sheet line items to classify:
{json.dumps([{"line_name": item["line_name"], "line_category": item["line_category"]} for item in line_items], indent=2)}

Return a JSON array with the same order as the input, where each item has:
{{
    "line_name": "exact name from input",
    "is_operating": true or false
}}

Return only valid JSON array, no additional text."""

    try:
        response_text = generate_content_safe(prompt)

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        classifications = json.loads(response_text)

        # Map classifications back to line items
        classification_map = {item["line_name"]: item["is_operating"] for item in classifications}

        # Add is_operating to each line item, using lookup first if available
        for item in line_items:
            line_name = item["line_name"]
            normalized_name = normalize_line_name(line_name)

            # First try authoritative lookup
            if normalized_name in normalized_lookup:
                lookup_value = normalized_lookup[normalized_name]
                item["is_operating"] = lookup_value == "Operating"
            # Then use LLM classification if available
            elif line_name in classification_map:
                item["is_operating"] = classification_map[line_name]
            else:
                # Default fallback: use heuristics
                # Cash, marketable securities, debt, equity, goodwill, intangibles, lease ROU -> Non-Operating
                line_lower = line_name.lower()
                if any(
                    keyword in line_lower
                    for keyword in [
                        "cash",
                        "marketable",
                        "securities",
                        "short-term investment",
                        "restricted cash",
                        "debt",
                        "loan",
                        "borrowing",
                        "equity",
                        "stock",
                        "treasury",
                        "goodwill",
                        "intangible",
                        "lease",
                        "right-of-use",
                        "rou asset",
                        "rou liability",
                    ]
                ):
                    item["is_operating"] = False
                # Working capital items, PPE -> Operating
                elif any(
                    keyword in line_lower
                    for keyword in [
                        "accounts receivable",
                        "inventory",
                        "inventories",
                        "accounts payable",
                        "accrued",
                        "prepaid",
                        "ppe",
                        "property",
                        "plant",
                        "equipment",
                    ]
                ):
                    item["is_operating"] = True
                # Default to operating
                else:
                    item["is_operating"] = True

        return line_items

    except Exception as e:
        print(f"Error classifying line items: {str(e)}")
        # Fallback: use lookup if available, otherwise default to operating
        for item in line_items:
            line_name = item["line_name"]
            normalized_name = normalize_line_name(line_name)

            if normalized_name in normalized_lookup:
                lookup_value = normalized_lookup[normalized_name]
                item["is_operating"] = lookup_value == "Operating"
            else:
                # Default to operating if classification fails
                item["is_operating"] = True
        return line_items


def extract_balance_sheet(
    document_id: str, file_path: str, time_period: str, max_retries: int = 3
) -> dict:
    """
    Main function to extract balance sheet with validation and retries.

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        time_period: Time period (e.g., "Q3 2023")
        max_retries: Maximum number of retry attempts

    Returns:
        Dictionary with balance sheet data and validation status
    """
    for attempt in range(max_retries):
        try:
            attempt_msg = f"Balance sheet extraction attempt {attempt + 1}/{max_retries}"
            print(attempt_msg)
            add_log(document_id, FinancialStatementMilestone.EXTRACTING_BALANCE_SHEET, attempt_msg)

            # Step 1: Find balance sheet section using embeddings
            balance_sheet_text, start_page, log_info = find_balance_sheet_section(
                document_id, file_path, time_period
            )

            if not balance_sheet_text:
                # Fallback: extract full document if embedding search fails
                fallback_msg = "Embedding search failed, extracting full document..."
                print(fallback_msg)
                add_log(
                    document_id, FinancialStatementMilestone.EXTRACTING_BALANCE_SHEET, fallback_msg
                )
                balance_sheet_text, _, _ = extract_text_from_pdf(file_path, max_pages=None)
                balance_sheet_text = balance_sheet_text[:50000]  # Limit to 50k chars
                extracted_msg = f"Extracted {len(balance_sheet_text)} characters from full document"
                print(extracted_msg)
                add_log(
                    document_id, FinancialStatementMilestone.EXTRACTING_BALANCE_SHEET, extracted_msg
                )
            else:
                # Log chunk/page information if available
                if log_info:
                    chunk_msg = f"Best match: chunk {log_info['best_chunk_index']} (pages {log_info['chunk_start_page']}-{log_info['chunk_end_page']})"
                    print(chunk_msg)
                    add_log(
                        document_id, FinancialStatementMilestone.EXTRACTING_BALANCE_SHEET, chunk_msg
                    )
                    pages_msg = f"Found balance sheet section (pages {log_info['start_extract_page']}-{log_info['end_extract_page']})"
                    print(pages_msg)
                    add_log(
                        document_id, FinancialStatementMilestone.EXTRACTING_BALANCE_SHEET, pages_msg
                    )
                found_msg = f"Found balance sheet section starting at page {start_page}, extracted {len(balance_sheet_text)} characters"
                print(found_msg)
                add_log(
                    document_id, FinancialStatementMilestone.EXTRACTING_BALANCE_SHEET, found_msg
                )

            # Step 2: Extract balance sheet using LLM
            extracted_data = extract_balance_sheet_llm(balance_sheet_text, time_period)

            # Ensure line_items exists and is a list
            if "line_items" not in extracted_data:
                extracted_data["line_items"] = []
            elif not isinstance(extracted_data["line_items"], list):
                print(
                    f"Warning: line_items is not a list, got {type(extracted_data['line_items'])}"
                )
                extracted_data["line_items"] = []

            extracted_count_msg = (
                f"Extracted {len(extracted_data.get('line_items', []))} line items"
            )
            print(extracted_count_msg)
            add_log(
                document_id,
                FinancialStatementMilestone.EXTRACTING_BALANCE_SHEET,
                extracted_count_msg,
            )

            # Step 3: Validate
            is_valid, errors = validate_balance_sheet(extracted_data["line_items"])

            if is_valid:
                validation_msg = "Validation passed"
                print(validation_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_BALANCE_SHEET,
                    validation_msg,
                )
                # Step 4: Classify line items
                classified_items = classify_line_items_llm(extracted_data["line_items"])
                extracted_data["line_items"] = classified_items
                extracted_data["is_valid"] = True
                extracted_data["validation_errors"] = []
                return extracted_data
            else:
                validation_failed_msg = (
                    f"Validation failed: {', '.join(errors[:3])}"  # Show first 3 errors
                )
                print(validation_failed_msg)
                add_log(
                    document_id,
                    FinancialStatementMilestone.EXTRACTING_BALANCE_SHEET,
                    validation_failed_msg,
                )
                if attempt < max_retries - 1:
                    continue  # Retry
                else:
                    # Return with errors on final attempt
                    classified_items = classify_line_items_llm(extracted_data["line_items"])
                    extracted_data["line_items"] = classified_items
                    extracted_data["is_valid"] = False
                    extracted_data["validation_errors"] = errors
                    return extracted_data

        except Exception as e:
            error_str = str(e).lower()
            # Check if it's an API error that was already retried at the API level
            is_api_error = any(
                keyword in error_str
                for keyword in [
                    "rate limit",
                    "quota",
                    "429",
                    "503",
                    "resource exhausted",
                    "service unavailable",
                    "too many requests",
                ]
            )

            # If it's an API error that failed after 3 retries, don't retry at agent level
            # (it's likely a persistent issue, not transient)
            if is_api_error:
                print(f"API error after retries on attempt {attempt + 1}: {str(e)}")
                raise  # Don't retry - API-level already tried 3 times

            # For other errors (validation, extraction issues), retry makes sense
            print(f"Error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                raise

    raise Exception(f"Failed to extract balance sheet after {max_retries} attempts")
