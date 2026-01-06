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


def _chunk_search_range(
    num_chunks: int, ignore_front_fraction: float = 0.0, ignore_back_fraction: float = 0.0
) -> range:
    ignore_front_count = int(num_chunks * ignore_front_fraction)
    ignore_back_count = int(num_chunks * ignore_back_fraction)
    start_index = ignore_front_count
    end_index = num_chunks - ignore_back_count
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
    rerank_query_texts: list[str] | None = None,
    ignore_front_fraction: float = 0.0,
    ignore_back_fraction: float = 0.0,
    chunk_rank: int = 0,
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

        resolved_chunk_size = chunk_size or chunk_metadata.get("chunk_size", 2)
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
        search_range = _chunk_search_range(num_chunks, ignore_front_fraction, ignore_back_fraction)

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
        best_chunk_index = -1
        best_score = -1.0

        if rerank_top_k > 0 and chunk_scores:
            # Get top K chunks by initial similarity
            top_chunks = sorted(chunk_scores, key=lambda item: item["similarity"], reverse=True)[
                :rerank_top_k
            ]

            # Rerank using rerank_query_texts if provided
            if rerank_query_texts:
                # Generate embeddings for rerank query texts
                rerank_query_embeddings = [
                    generate_embedding_safe(
                        query_text, max_chars=20000, task_type="retrieval_query"
                    )
                    for query_text in rerank_query_texts
                ]

                reranked = []
                for chunk_info in top_chunks:
                    chunk_index = chunk_info["chunk_index"]
                    chunk_embedding = load_chunk_embedding(document_id, chunk_index)

                    if not chunk_embedding:
                        chunk_text, _, _ = get_chunk_text(
                            file_path, chunk_index, resolved_chunk_size
                        )
                        chunk_embedding = generate_embedding_safe(
                            chunk_text[:20000], max_chars=20000, task_type="retrieval_document"
                        )
                        save_chunk_embedding(chunk_embedding, document_id, chunk_index)

                    # Calculate similarity with rerank queries (use max similarity across all rerank queries)
                    rerank_similarity = max(
                        cosine_similarity(chunk_embedding, rerank_query_embedding)
                        for rerank_query_embedding in rerank_query_embeddings
                    )
                    reranked.append(
                        {
                            "chunk_index": chunk_index,
                            "initial_similarity": chunk_info["similarity"],
                            "rerank_similarity": rerank_similarity,
                        }
                    )

                # Sort by rerank similarity
                reranked.sort(key=lambda item: item["rerank_similarity"], reverse=True)
                rerank_details = reranked

                # Select the Nth best chunk based on chunk_rank
                if chunk_rank < len(reranked):
                    selected_reranked = reranked[chunk_rank]
                    best_chunk_index = selected_reranked["chunk_index"]
                    best_score = selected_reranked["rerank_similarity"]
                else:
                    # If chunk_rank is out of bounds, use the last available chunk
                    if reranked:
                        selected_reranked = reranked[-1]
                        best_chunk_index = selected_reranked["chunk_index"]
                        best_score = selected_reranked["rerank_similarity"]
            else:
                # No rerank queries provided, use initial similarity
                rerank_details = [
                    {
                        "chunk_index": chunk_info["chunk_index"],
                        "similarity": chunk_info["similarity"],
                    }
                    for chunk_info in top_chunks
                ]

                # Select the Nth best chunk based on chunk_rank
                if chunk_rank < len(top_chunks):
                    selected_chunk = top_chunks[chunk_rank]
                    best_chunk_index = selected_chunk["chunk_index"]
                    best_score = selected_chunk["similarity"]
                else:
                    # If chunk_rank is out of bounds, use the last available chunk
                    if top_chunks:
                        selected_chunk = top_chunks[-1]
                        best_chunk_index = selected_chunk["chunk_index"]
                        best_score = selected_chunk["similarity"]
        else:
            # No reranking, use initial similarity scores
            sorted_chunks = sorted(chunk_scores, key=lambda item: item["similarity"], reverse=True)

            # Select the Nth best chunk based on chunk_rank
            if chunk_rank < len(sorted_chunks):
                selected_chunk = sorted_chunks[chunk_rank]
                best_chunk_index = selected_chunk["chunk_index"]
                best_score = selected_chunk["similarity"]
            else:
                # If chunk_rank is out of bounds, use the last available chunk
                if sorted_chunks:
                    selected_chunk = sorted_chunks[-1]
                    best_chunk_index = selected_chunk["chunk_index"]
                    best_score = selected_chunk["similarity"]

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

            rank_text = f" (rank {chunk_rank + 1})" if chunk_rank > 0 else ""
            print(
                f"Best match{rank_text}: chunk {best_chunk_index} (pages {chunk_start_page}-{chunk_end_page - 1}), "
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


def collect_top_chunk_texts(
    document_id: str,
    file_path: str,
    query_texts: list[str],
    *,
    top_k: int = 3,
    **kwargs,
) -> tuple[str | None, int | None, list[dict]]:
    """
    Collect and concatenate the top-k chunk texts for a query.

    Returns:
        Tuple of (combined_text, best_chunk_index, log_details)
    """
    texts: list[str] = []
    log_details: list[dict] = []
    best_chunk_index: int | None = None

    for rank in range(top_k):
        text, _, log_info = find_document_section(
            document_id=document_id,
            file_path=file_path,
            query_texts=query_texts,
            chunk_rank=rank,
            **kwargs,
        )
        if not text:
            continue

        if best_chunk_index is None and log_info:
            best_chunk_index = log_info.get("best_chunk_index")

        if text not in texts:
            texts.append(text)

        if log_info:
            log_details.append(log_info)

    combined_text = "\n\n".join(texts) if texts else None
    return combined_text, best_chunk_index, log_details
