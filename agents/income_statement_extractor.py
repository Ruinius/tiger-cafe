"""
Income statement extraction agent using Gemini LLM and embeddings
"""

import json

from app.utils.document_indexer import (
    get_chunk_metadata,
    get_chunk_text,
    load_chunk_embedding,
    save_chunk_embedding,
)
from app.utils.gemini_client import generate_content_safe, generate_embedding_safe
from app.utils.pdf_extractor import extract_text_from_pdf

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

    def cosine_similarity(a, b):
        dot_product = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        return dot_product / (norm_a * norm_b) if (norm_a * norm_b) > 0 else 0


def find_income_statement_section(
    document_id: str, file_path: str, time_period: str
) -> tuple[str | None, int | None]:
    """
    Use document embedding to locate the income statement section.
    May be called by various names (e.g., "consolidated statement of operations").

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        time_period: Time period to search for (e.g., "Q3 2023")

    Returns:
        Tuple of (extracted_text, start_page) or (None, None) if not found
    """
    try:
        # Load chunk metadata
        chunk_metadata = get_chunk_metadata(document_id)
        if not chunk_metadata:
            print(
                f"No chunk metadata found for document {document_id}, falling back to full document extraction"
            )
            return None, None

        chunk_size = chunk_metadata.get("chunk_size", 5)
        num_chunks = chunk_metadata.get("num_chunks", 0)

        if num_chunks == 0:
            print(f"No chunks found for document {document_id}")
            return None, None

        # Generate query embeddings for various income statement names
        query_texts = [
            "consolidated statement of operations",
            "income statement",
            "statement of operations",
            "consolidated income statement",
        ]

        query_embeddings = []
        for query_text in query_texts:
            query_embedding = generate_embedding_safe(
                query_text, max_chars=20000, task_type="retrieval_query"
            )
            query_embeddings.append(query_embedding)

        # Search through persisted chunk embeddings
        best_score = -1
        best_chunk_index = -1

        # Search through all chunks
        for chunk_index in range(num_chunks):
            # Load chunk embedding (or generate if missing)
            chunk_embedding = load_chunk_embedding(document_id, chunk_index)

            if not chunk_embedding:
                # Chunk embedding doesn't exist, generate it
                print(f"Chunk {chunk_index} embedding not found, generating...")
                chunk_text, start_page, end_page = get_chunk_text(
                    file_path, chunk_index, chunk_size
                )
                chunk_embedding = generate_embedding_safe(
                    chunk_text[:20000], max_chars=20000, task_type="retrieval_document"
                )
                save_chunk_embedding(chunk_embedding, document_id, chunk_index)

            # Calculate similarity with all query embeddings
            for query_embedding in query_embeddings:
                if HAS_NUMPY:
                    similarity = np.dot(chunk_embedding, query_embedding) / (
                        np.linalg.norm(chunk_embedding) * np.linalg.norm(query_embedding)
                    )
                else:
                    similarity = cosine_similarity(chunk_embedding, query_embedding)

                if similarity > best_score:
                    best_score = similarity
                    best_chunk_index = chunk_index

        # If we found a good match, extract text for that chunk and surrounding chunks
        if best_score > 0.3 and best_chunk_index >= 0:
            # Get text for the best matching chunk
            chunk_text, start_page, end_page = get_chunk_text(
                file_path, best_chunk_index, chunk_size
            )

            # Extract a larger section around the match (include adjacent chunks)
            # Get total pages
            import pdfplumber

            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)

            # Extract 2 chunks before and 2 chunks after (if available)
            start_extract_chunk = max(0, best_chunk_index - 2)
            end_extract_chunk = min(num_chunks, best_chunk_index + 3)

            start_extract_page = start_extract_chunk * chunk_size
            end_extract_page = min(total_pages, end_extract_chunk * chunk_size)

            extracted_text, _, _ = extract_text_from_pdf(file_path, max_pages=end_extract_page)
            if start_extract_page > 0:
                prev_text, _, _ = extract_text_from_pdf(file_path, max_pages=start_extract_page)
                extracted_text = extracted_text[len(prev_text) :]

            return extracted_text, start_extract_page

        return None, None

    except Exception as e:
        print(f"Error finding income statement section: {str(e)}")
        return None, None


def extract_income_statement_llm(text: str, time_period: str, currency: str | None = None) -> dict:
    """
    Use LLM to extract income statement line items exactly line by line.
    Also extracts revenue for the same period in the prior year.

    Args:
        text: Text containing income statement
        time_period: Time period (e.g., "Q3 2023")
        currency: Currency code if known

    Returns:
        Dictionary with income statement data
    """
    prompt = f"""Extract the income statement (also called "consolidated statement of operations" or "statement of earnings") from the following document text for the time period: {time_period}.
Extract the income statement exactly line by line, including all line items and their values starting with revenue.
If the company is foreign, extract the values in the local currency.

Also extract the revenue for the same period in the prior year (for year-over-year growth calculation).

Return a JSON object with the following structure:
{{
    "currency": currency code (extract from document),
    "unit": unit of measurement - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (extract from document, e.g., if values are in millions, use "millions"),
    "time_period": "{time_period}",
    "revenue_prior_year": revenue for the same period in the prior year (as number, null if not found),
    "revenue_prior_year_unit": unit for revenue_prior_year - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (usually same as "unit", null if revenue_prior_year is null),
    "line_items": [
        {{
            "line_name": "exact name as it appears in the document but do not include long notes in parentheses",
            "line_value": numeric value (as number, not string),
            "line_category": one of ["Revenue", "Costs", "Expenses", "Income", "Other"]
        }},
        ...
    ]
}}

IMPORTANT:
- Stop after the net income line item is extracted
- Extract values exactly as they appear (no rounding, include negative values if present)
- Include all line items, including but not limited to: Revenue, Cost of Revenue/Cost of Goods Sold, Gross Profit, Operating Expenses, Operating Income, Net Income, etc.
- Maintain the exact order of line items as they appear in the document
- Extract the currency code from the document if available
- Extract the unit from the document (look for notes like "in millions", "in thousands", "in billions", or "in ten thousands" for foreign stocks)
- Values should be numeric (not strings with commas or currency symbols)
- For revenue_prior_year, look for the same period in the prior year (e.g., if time_period is "Q3 2023", look for "Q3 2022" revenue)
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
        raise Exception(f"Error extracting income statement: {str(e)}")


def find_additional_data_section(document_id: str, file_path: str, time_period: str) -> str | None:
    """
    Use document embedding to locate sections containing shares outstanding, diluted shares, and amortization.

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        time_period: Time period to search for (e.g., "Q3 2023")

    Returns:
        Extracted text containing the relevant sections, or None if not found
    """
    try:
        # Load chunk metadata
        chunk_metadata = get_chunk_metadata(document_id)
        if not chunk_metadata:
            print(
                f"No chunk metadata found for document {document_id}, falling back to full document extraction"
            )
            return None

        # Generate query embeddings for various search terms
        query_texts = [
            "shares outstanding",
            "diluted shares",
            "amortization",
            "weighted average number of shares",
            "common shares outstanding",
            "basic shares",
        ]

        query_embeddings = []
        for query_text in query_texts:
            query_embedding = generate_embedding_safe(
                query_text, max_chars=20000, task_type="retrieval_query"
            )
            query_embeddings.append(query_embedding)

        chunk_size = chunk_metadata.get("chunk_size", 5)
        num_chunks = chunk_metadata.get("num_chunks", 0)

        if num_chunks == 0:
            print(f"No chunks found for document {document_id}")
            return None
        best_matches = []
        best_scores = []

        # Get total pages first
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)

        # Search through document in chunks
        for start_page in range(0, total_pages, chunk_size):
            end_page = min(start_page + chunk_size, total_pages)
            chunk_text, _, _ = extract_text_from_pdf(file_path, max_pages=end_page)
            # Get only the current chunk
            if start_page > 0:
                prev_text, _, _ = extract_text_from_pdf(file_path, max_pages=start_page)
                chunk_text = chunk_text[len(prev_text) :]

            # Generate embedding for chunk
            chunk_embedding = generate_embedding_safe(
                chunk_text[:20000], max_chars=20000, task_type="retrieval_document"
            )

            # Calculate similarity with all query embeddings
            for query_embedding in query_embeddings:
                if HAS_NUMPY:
                    similarity = np.dot(chunk_embedding, query_embedding) / (
                        np.linalg.norm(chunk_embedding) * np.linalg.norm(query_embedding)
                    )
                else:
                    similarity = cosine_similarity(chunk_embedding, query_embedding)

                if similarity > 0.3:  # Threshold for similarity
                    best_matches.append(chunk_text)
                    best_scores.append(similarity)

        # Combine all matching chunks
        if best_matches:
            # Remove duplicates and combine
            unique_matches = []
            seen_text = set()
            for match in best_matches:
                # Use first 1000 chars as a signature to detect duplicates
                signature = match[:1000]
                if signature not in seen_text:
                    seen_text.add(signature)
                    unique_matches.append(match)

            # Combine unique matches
            combined_text = "\n\n".join(unique_matches)
            return combined_text[:50000]  # Limit to 50k chars

        return None

    except Exception as e:
        print(f"Error finding additional data section: {str(e)}")
        return None


def extract_additional_data_llm(text: str, time_period: str) -> dict:
    """
    Extract additional data: total shares outstanding, diluted shares outstanding, and amortization.

    Args:
        text: Document text
        time_period: Time period (e.g., "Q3 2023")

    Returns:
        Dictionary with additional data
    """
    prompt = f"""Extract the following financial data from the document for the time period: {time_period}:

1. Basic shares outstanding (basic weighted average shares outstanding, common shares outstanding)
2. Diluted shares outstanding (diluted weighted average shares)
3. Amortization (amortization expense)

Return a JSON object with the following structure:
{{
    "basic_shares_outstanding": number (as number, not string, null if not found),
    "basic_shares_outstanding_unit": unit for basic_shares_outstanding - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (usually "ones", null if basic_shares_outstanding is null),
    "diluted_shares_outstanding": number (as number, not string, null if not found),
    "diluted_shares_outstanding_unit": unit for diluted_shares_outstanding - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (usually "ones", null if diluted_shares_outstanding is null),
    "amortization": number (as number, not string, null if not found),
    "amortization_unit": unit for amortization - one of ["ones", "thousands", "millions", "billions", "ten_thousands"] (usually same as income statement unit, null if amortization is null)
}}

IMPORTANT:
- Extract values exactly as they appear
- Values should be numeric (not strings with commas)
- If a value is not found, use null
- Look for these values in the income statement, notes, or financial highlights sections
- Extract units from the document (shares are usually in "ones", amortization usually matches the income statement unit)
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
        return result

    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse LLM response as JSON: {str(e)}")
    except Exception as e:
        raise Exception(f"Error extracting additional data: {str(e)}")


def validate_income_statement(
    line_items: list[dict], revenue: float | None = None
) -> tuple[bool, list[str]]:
    """
    Validate income statement calculations.

    Args:
        line_items: List of income statement line items
        revenue: Revenue value (if available)

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check if line_items is empty
    if not line_items or len(line_items) == 0:
        errors.append("Income statement is empty - no line items extracted")
        return False, errors

    # Check if we have at least some meaningful line items (not just empty strings)
    valid_items = [
        item for item in line_items if item.get("line_name") and item.get("line_name").strip()
    ]
    if len(valid_items) == 0:
        errors.append("Income statement has no valid line items")
        return False, errors

    # Convert to dictionary for easier lookup
    items_dict = {item["line_name"].lower(): item["line_value"] for item in line_items}

    # Find key values
    revenue_value = None
    cost_of_revenue = None
    gross_profit = None
    operating_expenses = None
    operating_income = None
    net_income = None

    for key, value in items_dict.items():
        if "revenue" in key and "total" not in key and "net" not in key:
            if revenue_value is None or "net revenue" in key or "total revenue" in key:
                revenue_value = value
        elif (
            "cost of revenue" in key or "cost of goods sold" in key or "cogs" in key
        ) and "total" not in key:
            cost_of_revenue = value
        elif "gross profit" in key:
            gross_profit = value
        elif (
            "operating expenses" in key or "total operating expenses" in key
        ) and "income" not in key:
            operating_expenses = value
        elif "operating income" in key or "income from operations" in key:
            operating_income = value
        elif "net income" in key and "per share" not in key:
            net_income = value

    # Use provided revenue if available
    if revenue is not None:
        revenue_value = revenue

    # Validate gross profit: Revenue - Cost of Revenue = Gross Profit
    if revenue_value is not None and cost_of_revenue is not None and gross_profit is not None:
        calculated_gross_profit = revenue_value - cost_of_revenue
        diff = abs(gross_profit - calculated_gross_profit)
        if diff > 0.01:
            errors.append(
                f"Gross profit calculation mismatch: reported={gross_profit}, calculated (Revenue - Cost of Revenue)={calculated_gross_profit}"
            )

    # Validate operating income: Gross Profit - Operating Expenses = Operating Income
    if gross_profit is not None and operating_expenses is not None and operating_income is not None:
        calculated_operating_income = gross_profit - operating_expenses
        diff = abs(operating_income - calculated_operating_income)
        if diff > 0.01:
            errors.append(
                f"Operating income calculation mismatch: reported={operating_income}, calculated (Gross Profit - Operating Expenses)={calculated_operating_income}"
            )

    # Validate net income (if we can calculate it)
    # Net Income = Operating Income - Other Expenses + Other Income - Taxes
    # This is more complex, so we'll just check if net income exists and is reasonable
    if net_income is None:
        # Try to find it with alternative names
        for key, value in items_dict.items():
            if ("net income" in key or "net earnings" in key) and "per share" not in key:
                net_income = value
                break

    # Check if we have at least one key income statement item (revenue, gross profit, operating income, or net income)
    # This ensures we didn't get an empty or invalid income statement
    if (
        revenue_value is None
        and gross_profit is None
        and operating_income is None
        and net_income is None
    ):
        errors.append(
            "Income statement is missing key items (Revenue, Gross Profit, Operating Income, or Net Income)"
        )

    return len(errors) == 0, errors


def classify_line_items_llm(line_items: list[dict]) -> list[dict]:
    """
    Use LLM to categorize each income statement line item as operating or non-operating.

    Args:
        line_items: List of income statement line items

    Returns:
        List of line items with is_operating classification added
    """
    # Prepare context for LLM
    items_text = "\n".join([f"- {item['line_name']}" for item in line_items])

    prompt = f"""Classify each income statement line item as operating or non-operating.

Operating items are related to the core business operations:
- Revenue, Cost of Revenue, Operating Expenses, Operating Income
- Sales, Marketing, R&D, General & Administrative expenses
- Items that are part of normal business operations

Non-operating items are not part of core operations:
- Interest income/expense
- Foreign exchange gains/losses
- Investment gains/losses
- Restructuring charges
- One-time items
- Tax expenses (though taxes are typically non-operating, they may be shown separately)

Line items:
{items_text}

Return a JSON object with the following structure:
{{
    "classifications": [
        {{
            "line_name": "exact line name as provided",
            "is_operating": true or false
        }},
        ...
    ]
}}

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
        classifications = {
            item["line_name"]: item["is_operating"] for item in result.get("classifications", [])
        }

        # Add classifications to line items
        classified_items = []
        for item in line_items:
            item_copy = item.copy()
            item_copy["is_operating"] = classifications.get(item["line_name"], None)
            classified_items.append(item_copy)

        return classified_items

    except Exception as e:
        print(f"Error classifying income statement line items: {str(e)}")
        # Return items without classification if classification fails
        return line_items


def extract_income_statement(
    document_id: str, file_path: str, time_period: str, max_retries: int = 3
) -> dict:
    """
    Main function to extract income statement with validation and retries.

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        time_period: Time period (e.g., "Q3 2023")
        max_retries: Maximum number of retry attempts

    Returns:
        Dictionary with income statement data and validation status
    """
    for attempt in range(max_retries):
        try:
            # Step 1: Find income statement section using embeddings
            income_statement_text, start_page = find_income_statement_section(
                document_id, file_path, time_period
            )

            if not income_statement_text:
                # Fallback: extract full document if embedding search fails
                print(
                    f"Embedding search failed, extracting full document for attempt {attempt + 1}"
                )
                income_statement_text, _, _ = extract_text_from_pdf(file_path, max_pages=None)
                income_statement_text = income_statement_text[:50000]  # Limit to 50k chars

            # Step 2: Extract income statement using LLM
            extracted_data = extract_income_statement_llm(income_statement_text, time_period)

            # Step 3: Find and extract additional data (shares outstanding, amortization) using embedding search
            additional_data_text = find_additional_data_section(document_id, file_path, time_period)
            if additional_data_text:
                additional_data = extract_additional_data_llm(additional_data_text, time_period)
            else:
                # Fallback: try with income statement text if embedding search fails
                print(
                    "Embedding search for additional data failed, trying with income statement text"
                )
                additional_data = extract_additional_data_llm(income_statement_text, time_period)
            extracted_data.update(additional_data)

            # Step 4: Validate
            extracted_data.get("revenue_prior_year")  # Use revenue from extraction
            # Find current revenue from line items
            current_revenue = None
            for item in extracted_data.get("line_items", []):
                if (
                    "revenue" in item.get("line_name", "").lower()
                    and "total" not in item.get("line_name", "").lower()
                ):
                    current_revenue = item.get("line_value")
                    break

            is_valid, errors = validate_income_statement(
                extracted_data.get("line_items", []), current_revenue
            )

            if is_valid:
                # Step 5: Classify line items
                classified_items = classify_line_items_llm(extracted_data["line_items"])
                extracted_data["line_items"] = classified_items
                extracted_data["is_valid"] = True
                extracted_data["validation_errors"] = []

                # Calculate revenue growth YoY
                if (
                    current_revenue is not None
                    and extracted_data.get("revenue_prior_year") is not None
                ):
                    prior_revenue = extracted_data["revenue_prior_year"]
                    if prior_revenue > 0:
                        revenue_growth = ((current_revenue - prior_revenue) / prior_revenue) * 100
                        extracted_data["revenue_growth_yoy"] = revenue_growth

                return extracted_data
            else:
                print(f"Validation failed on attempt {attempt + 1}: {errors}")
                if attempt < max_retries - 1:
                    continue  # Retry
                else:
                    # Return with errors on final attempt
                    classified_items = classify_line_items_llm(extracted_data["line_items"])
                    extracted_data["line_items"] = classified_items
                    extracted_data["is_valid"] = False
                    extracted_data["validation_errors"] = errors

                    # Still calculate revenue growth if possible
                    if (
                        current_revenue is not None
                        and extracted_data.get("revenue_prior_year") is not None
                    ):
                        prior_revenue = extracted_data["revenue_prior_year"]
                        if prior_revenue > 0:
                            revenue_growth = (
                                (current_revenue - prior_revenue) / prior_revenue
                            ) * 100
                            extracted_data["revenue_growth_yoy"] = revenue_growth

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

    raise Exception(f"Failed to extract income statement after {max_retries} attempts")
