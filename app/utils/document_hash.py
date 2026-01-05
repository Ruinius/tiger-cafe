"""
Document hashing utilities for duplicate detection
"""

import hashlib


def generate_document_hash(text: str) -> str:
    """
    Generate a SHA-256 hash from document text for duplicate detection.

    Args:
        text: Extracted text from the document

    Returns:
        Hexadecimal hash string
    """
    # Normalize text: remove extra whitespace and convert to lowercase
    normalized_text = " ".join(text.split()).lower()

    # Generate SHA-256 hash
    hash_object = hashlib.sha256(normalized_text.encode("utf-8"))
    hash_hex = hash_object.hexdigest()

    return hash_hex


def generate_document_hash_from_file(file_path: str, max_pages: int | None = 10) -> str:
    """
    Generate a hash from a PDF file by extracting text from first few pages.
    This is useful for quick duplicate detection without full text extraction.

    Args:
        file_path: Path to the PDF file
        max_pages: Maximum number of pages to use for hashing (default: 10)

    Returns:
        Hexadecimal hash string
    """
    from app.utils.pdf_extractor import extract_text_from_pdf

    try:
        extracted_text, _, _ = extract_text_from_pdf(file_path, max_pages=max_pages)
        return generate_document_hash(extracted_text)
    except Exception as e:
        # Preserve original exception context
        raise Exception(f"Error generating hash from file '{file_path}': {str(e)}") from e
