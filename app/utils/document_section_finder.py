"""
Utilities for finding relevant document sections using embeddings.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.utils.document_indexer import (
    get_chunk_metadata,
    get_chunk_text,
    load_chunk_embedding,
    save_chunk_embedding,
)
from app.utils.gemini_client import generate_embedding_safe

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def cosine_similarity(a: Iterable[float], b: Iterable[float]) -> float:
    if HAS_NUMPY:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    dot_product = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    return dot_product / (norm_a * norm_b) if (norm_a * norm_b) > 0 else 0


def _extract_page_range_text(file_path: str, start_page: int, end_page: int) -> str:
    import pdfplumber

    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        total_pages = len(pdf.pages)
        clamped_start = max(0, min(start_page, total_pages))
        clamped_end = max(clamped_start, min(end_page, total_pages))

        for page_index in range(clamped_start, clamped_end):
            page_text = pdf.pages[page_index].extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n\n".join(text_parts)


def find_document_section(
    document_id: str,
    file_path: str,
    query_texts: list[str],
    chunk_size: int | None = None,
    score_threshold: float = 0.3,
    pages_before: int = 1,
    pages_after: int = 1,
) -> tuple[str | None, int | None]:
    """
    Use document embeddings to locate relevant sections for the provided queries.

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        query_texts: Query phrases to search for
        chunk_size: Size of a chunk in pages; falls back to indexed metadata
        score_threshold: Minimum similarity score to consider a match
        pages_before: Number of pages to include before the best matching chunk (default: 1)
        pages_after: Number of pages to include after the best matching chunk (default: 1)

    Returns:
        Tuple of (extracted_text, start_page) or (None, None) if not found
    """
    try:
        chunk_metadata = get_chunk_metadata(document_id)
        if not chunk_metadata:
            print(
                f"No chunk metadata found for document {document_id}, falling back to full document extraction"
            )
            return None, None

        resolved_chunk_size = chunk_size or chunk_metadata.get("chunk_size", 5)
        num_chunks = chunk_metadata.get("num_chunks", 0)

        if num_chunks == 0:
            print(f"No chunks found for document {document_id}")
            return None, None

        # Get total pages
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)

        # Generate query embeddings for all query texts
        query_embeddings = [
            generate_embedding_safe(query_text, max_chars=20000, task_type="retrieval_query")
            for query_text in query_texts
        ]

        best_score = -1.0
        best_chunk_index = -1

        # Search through all chunks to find the best match
        for chunk_index in range(num_chunks):
            chunk_embedding = load_chunk_embedding(document_id, chunk_index)

            if not chunk_embedding:
                print(f"Chunk {chunk_index} embedding not found, generating...")
                chunk_text, _, _ = get_chunk_text(file_path, chunk_index, resolved_chunk_size)
                chunk_embedding = generate_embedding_safe(
                    chunk_text[:20000], max_chars=20000, task_type="retrieval_document"
                )
                save_chunk_embedding(chunk_embedding, document_id, chunk_index)

            # Check similarity with all query embeddings and keep the best match
            for query_embedding in query_embeddings:
                similarity = cosine_similarity(chunk_embedding, query_embedding)
                if similarity > best_score:
                    best_score = similarity
                    best_chunk_index = chunk_index

        if best_score > score_threshold and best_chunk_index >= 0:
            # Calculate the page range for the best matching chunk
            chunk_start_page = best_chunk_index * resolved_chunk_size
            chunk_end_page = min(chunk_start_page + resolved_chunk_size, total_pages)

            # Extract pages: pages_before pages before the chunk start,
            # the entire chunk, and pages_after pages after the chunk end
            start_extract_page = max(0, chunk_start_page - pages_before)
            end_extract_page = min(total_pages, chunk_end_page + pages_after)

            log_info = {
                "best_chunk_index": best_chunk_index,
                "chunk_start_page": chunk_start_page,
                "chunk_end_page": chunk_end_page - 1,
                "similarity": best_score,
                "start_extract_page": start_extract_page,
                "end_extract_page": end_extract_page - 1,
            }

            print(
                f"Best match: chunk {best_chunk_index} (pages {chunk_start_page}-{chunk_end_page - 1}), "
                f"similarity={best_score:.3f}, extracting pages {start_extract_page}-{end_extract_page - 1}"
            )

            extracted_text = _extract_page_range_text(
                file_path, start_extract_page, end_extract_page
            )
            return extracted_text, start_extract_page, log_info

        print(f"No match found above threshold {score_threshold}. Best score: {best_score:.3f}")
        return None, None, None

    except Exception as e:
        print(f"Error finding document section: {str(e)}")
        import traceback

        traceback.print_exc()
        return None, None
