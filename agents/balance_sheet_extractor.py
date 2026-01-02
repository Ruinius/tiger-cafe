"""
Balance sheet extraction agent using Gemini LLM and embeddings
"""

import google.generativeai as genai
from config.config import GEMINI_API_KEY, DEFAULT_MODEL, TEMPERATURE, EMBEDDING_MODEL
from app.models.document import DocumentType
from app.utils.document_indexer import load_embedding
from app.utils.pdf_extractor import extract_text_from_pdf
from typing import Dict, List, Optional, Tuple
import json
import os
import csv
from datetime import datetime

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    # Fallback for cosine similarity without numpy
    def cosine_similarity(a, b):
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        return dot_product / (norm_a * norm_b) if (norm_a * norm_b) > 0 else 0


# Initialize Gemini
genai.configure(api_key=GEMINI_API_KEY)


def load_balance_sheet_items_csv() -> Dict[str, str]:
    """
    Load balance sheet items CSV for classification context.
    
    Returns:
        Dictionary mapping line names to typical classifications
    """
    csv_path = os.path.join("data", "balance_sheet_items.csv")
    items = {}
    
    if os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                line_name = row.get('line_name', '').strip().lower()
                classification = row.get('typical_classification', 'operating').strip()
                items[line_name] = classification
    
    return items


def find_balance_sheet_section(document_id: str, file_path: str, time_period: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Use document embedding to locate the consolidated balance sheet section.
    
    Args:
        document_id: Document ID
        file_path: Path to PDF file
        time_period: Time period to search for (e.g., "Q3 2023")
    
    Returns:
        Tuple of (extracted_text, start_page) or (None, None) if not found
    """
    try:
        # Load document embedding
        doc_embedding = load_embedding(document_id)
        if not doc_embedding:
            print(f"No embedding found for document {document_id}")
            return None, None
        
        # Generate query embedding for "consolidated balance sheet"
        query_text = f"consolidated balance sheet {time_period}"
        query_embedding = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=query_text,
            task_type="retrieval_query"
        )['embedding']
        
        # Extract text from PDF in chunks (search through pages)
        # We'll search through the document in 10-page chunks
        chunk_size = 10
        best_match = None
        best_score = -1
        best_start_page = 0
        
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
                chunk_text = chunk_text[len(prev_text):]
            
            # Generate embedding for chunk
            chunk_embedding = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=chunk_text[:20000],  # Limit chunk size
                task_type="retrieval_document"
            )['embedding']
            
            # Calculate cosine similarity
            if HAS_NUMPY:
                similarity = np.dot(query_embedding, chunk_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(chunk_embedding)
                )
            else:
                similarity = cosine_similarity(query_embedding, chunk_embedding)
            
            if similarity > best_score:
                best_score = similarity
                best_match = chunk_text
                best_start_page = start_page
        
        # If we found a reasonable match, extract a larger section around it
        if best_score > 0.3:  # Threshold for relevance
            # Extract 20 pages around the best match
            start_extract = max(0, best_start_page - 5)
            end_extract = min(total_pages, best_start_page + chunk_size + 15)
            extracted_text, _, _ = extract_text_from_pdf(file_path, max_pages=end_extract)
            if start_extract > 0:
                prev_text, _, _ = extract_text_from_pdf(file_path, max_pages=start_extract)
                extracted_text = extracted_text[len(prev_text):]
            
            return extracted_text, best_start_page
        
        return None, None
    
    except Exception as e:
        print(f"Error finding balance sheet section: {str(e)}")
        return None, None


def extract_balance_sheet_llm(text: str, time_period: str, currency: Optional[str] = None) -> Dict:
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

Return a JSON object with the following structure:
{{
    "currency": "USD" or other currency code (extract from document if available),
    "time_period": "{time_period}",
    "line_items": [
        {{
            "line_name": "exact name as it appears in the document",
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
- Values should be numeric (not strings with commas or currency symbols)

Document text:
{text[:30000]}  # Limit to 30k characters

Return only valid JSON, no additional text."""

    try:
        model = genai.GenerativeModel(
            model_name=DEFAULT_MODEL,
            generation_config={
                "temperature": TEMPERATURE,
            }
        )
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
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
        raise Exception(f"Error extracting balance sheet: {str(e)}")


def validate_balance_sheet(line_items: List[Dict]) -> Tuple[bool, List[str]]:
    """
    Validate balance sheet calculations.
    
    Args:
        line_items: List of balance sheet line items
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Convert to dictionary for easier lookup
    items_dict = {item['line_name'].lower(): item['line_value'] for item in line_items}
    
    # Find key totals
    current_assets = None
    total_assets = None
    current_liabilities = None
    total_liabilities = None
    total_equity = None
    total_liabilities_equity = None
    
    for key, value in items_dict.items():
        if 'current assets' in key and 'total' in key:
            current_assets = value
        elif 'total assets' in key and 'liabilities' not in key:
            total_assets = value
        elif 'current liabilities' in key and 'total' in key:
            current_liabilities = value
        elif 'total liabilities' in key and 'equity' not in key:
            total_liabilities = value
        elif 'total equity' in key and 'liabilities' not in key:
            total_equity = value
        elif 'total liabilities and equity' in key or 'total liabilities and shareholders' in key:
            total_liabilities_equity = value
    
    # Calculate sums from line items
    # Only sum base line items, exclude any totals or subtotals
    # Exclude items that are totals themselves (by name or category)
    def is_total_item(item):
        """Check if an item is a total/subtotal line"""
        name_lower = item['line_name'].lower()
        category = item.get('line_category', '')
        # Exclude if name contains total keywords or category is a total category
        total_keywords = ['total', 'subtotal', 'sum']
        return (any(keyword in name_lower for keyword in total_keywords) or
                'Total' in category)
    
    # Only include base line items (not totals) in the EXACT correct category
    # Be very explicit about category matching to avoid confusion
    current_assets_sum = sum(
        item['line_value'] for item in line_items
        if (item.get('line_category', '').strip() == 'Current Assets' 
            and not is_total_item(item)
            and 'non-current' not in item.get('line_name', '').lower())
    )
    
    total_assets_sum = sum(
        item['line_value'] for item in line_items
        if (item.get('line_category', '').strip() in ['Current Assets', 'Non-Current Assets'] 
            and not is_total_item(item))
    )
    
    current_liabilities_sum = sum(
        item['line_value'] for item in line_items
        if (item.get('line_category', '').strip() == 'Current Liabilities' 
            and not is_total_item(item)
            and 'non-current' not in item.get('line_name', '').lower())
    )
    
    total_liabilities_sum = sum(
        item['line_value'] for item in line_items
        if (item.get('line_category', '').strip() in ['Current Liabilities', 'Non-Current Liabilities'] 
            and not is_total_item(item))
    )
    
    # Validate current assets
    if current_assets is not None:
        diff = abs(current_assets - current_assets_sum)
        if diff > 0.01:  # Allow small rounding differences
            errors.append(f"Current assets sum mismatch: reported={current_assets}, calculated={current_assets_sum}")
    
    # Validate total assets
    if total_assets is not None:
        diff = abs(total_assets - total_assets_sum)
        if diff > 0.01:
            errors.append(f"Total assets sum mismatch: reported={total_assets}, calculated={total_assets_sum}")
    
    # Validate current liabilities
    if current_liabilities is not None:
        diff = abs(current_liabilities - current_liabilities_sum)
        if diff > 0.01:
            errors.append(f"Current liabilities sum mismatch: reported={current_liabilities}, calculated={current_liabilities_sum}")
    
    # Validate total liabilities
    if total_liabilities is not None:
        diff = abs(total_liabilities - total_liabilities_sum)
        if diff > 0.01:
            errors.append(f"Total liabilities sum mismatch: reported={total_liabilities}, calculated={total_liabilities_sum}")
    
    # Validate balance sheet equation: Assets = Liabilities + Equity
    if total_assets is not None and total_liabilities is not None and total_equity is not None:
        liabilities_equity_sum = total_liabilities + total_equity
        diff = abs(total_assets - liabilities_equity_sum)
        if diff > 0.01:
            errors.append(f"Balance sheet equation mismatch: Assets={total_assets}, Liabilities+Equity={liabilities_equity_sum}")
    
    # Validate total liabilities and equity
    if total_liabilities_equity is not None and total_assets is not None:
        diff = abs(total_assets - total_liabilities_equity)
        if diff > 0.01:
            errors.append(f"Total liabilities and equity mismatch: reported={total_liabilities_equity}, should equal total assets={total_assets}")
    
    return len(errors) == 0, errors


def classify_line_items_llm(line_items: List[Dict]) -> List[Dict]:
    """
    Use LLM to categorize each balance sheet line item as operating or non-operating.
    
    Args:
        line_items: List of balance sheet line items
    
    Returns:
        List of line items with is_operating field added
    """
    # Load reference CSV
    reference_items = load_balance_sheet_items_csv()
    
    # Prepare context from CSV
    csv_context = "\n".join([
        f"- {name}: {classification}"
        for name, classification in reference_items.items()
    ])
    
    prompt = f"""Classify each balance sheet line item as either "operating" or "non-operating" based on whether it relates to the company's core business operations.

Reference classifications (use as guidance, but use your best judgment):
{csv_context}

Balance sheet line items to classify:
{json.dumps([{"line_name": item['line_name'], "line_category": item['line_category']} for item in line_items], indent=2)}

Return a JSON array with the same order as the input, where each item has:
{{
    "line_name": "exact name from input",
    "is_operating": true or false
}}

Return only valid JSON array, no additional text."""

    try:
        model = genai.GenerativeModel(
            model_name=DEFAULT_MODEL,
            generation_config={
                "temperature": TEMPERATURE,
            }
        )
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        classifications = json.loads(response_text)
        
        # Map classifications back to line items
        classification_map = {item['line_name']: item['is_operating'] for item in classifications}
        
        # Add is_operating to each line item
        for item in line_items:
            item['is_operating'] = classification_map.get(item['line_name'], True)  # Default to operating
        
        return line_items
    
    except Exception as e:
        print(f"Error classifying line items: {str(e)}")
        # Default all to operating if classification fails
        for item in line_items:
            item['is_operating'] = True
        return line_items


def extract_balance_sheet(
    document_id: str,
    file_path: str,
    time_period: str,
    max_retries: int = 3
) -> Dict:
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
            # Step 1: Find balance sheet section using embeddings
            balance_sheet_text, start_page = find_balance_sheet_section(document_id, file_path, time_period)
            
            if not balance_sheet_text:
                # Fallback: extract full document if embedding search fails
                print(f"Embedding search failed, extracting full document for attempt {attempt + 1}")
                balance_sheet_text, _, _ = extract_text_from_pdf(file_path, max_pages=None)
                balance_sheet_text = balance_sheet_text[:50000]  # Limit to 50k chars
            
            # Step 2: Extract balance sheet using LLM
            extracted_data = extract_balance_sheet_llm(balance_sheet_text, time_period)
            
            # Step 3: Validate
            is_valid, errors = validate_balance_sheet(extracted_data['line_items'])
            
            if is_valid:
                # Step 4: Classify line items
                classified_items = classify_line_items_llm(extracted_data['line_items'])
                extracted_data['line_items'] = classified_items
                extracted_data['is_valid'] = True
                extracted_data['validation_errors'] = []
                return extracted_data
            else:
                print(f"Validation failed on attempt {attempt + 1}: {errors}")
                if attempt < max_retries - 1:
                    continue  # Retry
                else:
                    # Return with errors on final attempt
                    classified_items = classify_line_items_llm(extracted_data['line_items'])
                    extracted_data['line_items'] = classified_items
                    extracted_data['is_valid'] = False
                    extracted_data['validation_errors'] = errors
                    return extracted_data
        
        except Exception as e:
            print(f"Error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                raise
    
    raise Exception(f"Failed to extract balance sheet after {max_retries} attempts")

