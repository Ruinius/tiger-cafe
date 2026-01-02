"""
PDF text extraction utilities
"""

import pdfplumber
from typing import Optional
import os


def extract_text_from_pdf(file_path: str, max_pages: Optional[int] = 5) -> tuple[str, int, int]:
    """
    Extract text from the first few pages of a PDF file.
    
    Args:
        file_path: Path to the PDF file
        max_pages: Maximum number of pages to extract (default: 5)
    
    Returns:
        Tuple of (extracted_text, total_pages, character_count)
    """
    text_parts = []
    total_pages = 0
    character_count = 0
    
    try:
        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)
            
            if max_pages is None:
                # Extract all pages
                pages_to_extract = total_pages
            else:
                pages_to_extract = min(max_pages, total_pages)
            
            for i in range(pages_to_extract):
                page = pdf.pages[i]
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
                    character_count += len(page_text)
            
            extracted_text = "\n\n".join(text_parts)
            return extracted_text, total_pages, character_count
    
    except Exception as e:
        raise Exception(f"Error extracting text from PDF: {str(e)}")


def get_pdf_metadata(file_path: str) -> dict:
    """
    Get basic metadata about a PDF file.
    
    Args:
        file_path: Path to the PDF file
    
    Returns:
        Dictionary with metadata (pages, file_size, etc.)
    """
    metadata = {
        "file_size": os.path.getsize(file_path),
        "pages": 0
    }
    
    try:
        with pdfplumber.open(file_path) as pdf:
            metadata["pages"] = len(pdf.pages)
    except Exception:
        pass
    
    return metadata

