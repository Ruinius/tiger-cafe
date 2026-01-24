"""
PDF text extraction utilities
"""

import logging
import os

import pdfplumber

logger = logging.getLogger(__name__)

# Suppress pdfminer FontBBox warnings
logging.getLogger("pdfminer").setLevel(logging.ERROR)


class PDFExtractionError(Exception):
    """Custom exception for PDF extraction errors"""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


class PDFMetadataError(Exception):
    """Custom exception for PDF metadata errors"""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


def extract_text_from_pdf(file_path: str, max_pages: int | None = 5) -> tuple[str, int, int]:
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

    except PDFExtractionError:
        # Re-raise our custom exceptions as-is
        raise
    except Exception as e:
        # Wrap other exceptions to preserve context
        raise PDFExtractionError(
            f"Error extracting text from PDF '{file_path}': {str(e)}", original_error=e
        ) from e


def get_pdf_metadata(file_path: str) -> dict:
    """
    Get basic metadata about a PDF file.

    Args:
        file_path: Path to the PDF file

    Returns:
        Dictionary with metadata (pages, file_size, etc.)
    """
    metadata = {"file_size": os.path.getsize(file_path), "pages": 0}

    try:
        with pdfplumber.open(file_path) as pdf:
            metadata["pages"] = len(pdf.pages)
    except Exception as e:
        # Log metadata errors but don't fail the operation
        logger.warning(
            f"Error extracting PDF metadata from '{file_path}': {str(e)}",
            exc_info=True,
        )
        # Pages will remain 0 if extraction fails

    return metadata
