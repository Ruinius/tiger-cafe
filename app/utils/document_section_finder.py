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


def _numeric_density(text: str) -> float:
    if not text:
        return 0.0
    digit_count = sum(1 for char in text if char.isdigit())
    alpha_count = sum(1 for char in text if char.isalpha())
    return digit_count / max(1, digit_count + alpha_count)


def _chunk_search_range(num_chunks: int, ignore_fraction: float) -> range:
    ignore_count = int(num_chunks * ignore_fraction)
    start_index = ignore_count
    end_index = num_chunks - ignore_count
    if start_index >= end_index:
        start_index = 0
        end_index = num_chunks
    return range(start_index, end_index)


def find_document_section(
    document_id: str,
    file_path: str,
    query_texts: list[str],
    chunk_size: int | None = None,
    score_threshold: float = 0.3,
    pages_before: int = 1,
    pages_after: int = 1,
    rerank_top_k: int = 0,
    numeric_density_weight: float = 0.2,
    ignore_edge_fraction: float = 0.1,
) -> tuple[str | None, int | None, dict | None]:
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

        resolved_chunk_size = chunk_size or chunk_metadata.get("chunk_size", 1)
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
        chunk_scores: list[dict] = []
        search_range = _chunk_search_range(num_chunks, ignore_edge_fraction)

        # Search through all chunks to find the best match
        for chunk_index in search_range:
            chunk_embedding = load_chunk_embedding(document_id, chunk_index)

            if not chunk_embedding:
                print(f"Chunk {chunk_index} embedding not found, generating...")
                chunk_text, _, _ = get_chunk_text(file_path, chunk_index, resolved_chunk_size)
                chunk_embedding = generate_embedding_safe(
                    chunk_text[:20000], max_chars=20000, task_type="retrieval_document"
                )
                save_chunk_embedding(chunk_embedding, document_id, chunk_index)

            # Check similarity with all query embeddings and keep the best match
            best_chunk_similarity = max(
                cosine_similarity(chunk_embedding, query_embedding)
                for query_embedding in query_embeddings
            )
            if best_chunk_similarity > best_score:
                best_score = best_chunk_similarity
                best_chunk_index = chunk_index
            chunk_scores.append({"chunk_index": chunk_index, "similarity": best_chunk_similarity})

        rerank_details = None
        if rerank_top_k > 0 and chunk_scores:
            top_chunks = sorted(chunk_scores, key=lambda item: item["similarity"], reverse=True)[
                :rerank_top_k
            ]
            reranked = []
            for chunk_info in top_chunks:
                chunk_text, _, _ = get_chunk_text(
                    file_path, chunk_info["chunk_index"], resolved_chunk_size
                )
                density = _numeric_density(chunk_text)
                rerank_score = chunk_info["similarity"] + (numeric_density_weight * density)
                reranked.append(
                    {
                        "chunk_index": chunk_info["chunk_index"],
                        "similarity": chunk_info["similarity"],
                        "numeric_density": density,
                        "rerank_score": rerank_score,
                    }
                )
            best_reranked = max(reranked, key=lambda item: item["rerank_score"])
            best_chunk_index = best_reranked["chunk_index"]
            best_score = best_reranked["similarity"]
            rerank_details = reranked

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
                "search_range": {"start": search_range.start, "end": search_range.stop - 1},
            }
            if rerank_details is not None:
                log_info["rerank_top_k"] = rerank_top_k
                log_info["rerank_details"] = rerank_details

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
        return None, None, None
