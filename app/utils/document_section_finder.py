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


def _count_numbers(text: str) -> int:
    """Count occurrences of numerical values in text."""
    if not text:
        return 0
    import re

    # Match numbers like 1,234.56, (123), -456.0, etc.
    # Specifically looking for digit sequences, possibly with commas/decimals
    # and possibly wrapped in parentheses for negative numbers.
    number_pattern = r"\(?\b\d+(?:,\d+)*(?:\.\d+)?\)?\b"
    matches = re.findall(number_pattern, text)
    return len(matches)


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


def _penalize_edge_chunks(chunks: list[dict], search_range: range) -> list[dict]:
    """
    If the top-ranked chunk is at the boundaries of the search range,
    demote it by 2 positions. This helps avoid edge-case false positives.
    """
    if not chunks or len(chunks) < 2:
        return chunks

    first_chunk_index = search_range.start
    last_chunk_index = search_range.stop - 1

    top_chunk = chunks[0]
    if top_chunk["chunk_index"] in (first_chunk_index, last_chunk_index):
        target_index = min(2, len(chunks) - 1)
        if target_index > 0:
            removed = chunks.pop(0)
            chunks.insert(target_index, removed)
    return chunks


def _find_document_section_legacy(
    document_id: str,
    file_path: str,
    query_texts: list[str],
    chunk_size: int | None = None,
    score_threshold: float = 0.3,
    chars_before: int = 2500,
    chars_after: int = 2500,
    rerank_top_k: int = 0,
    rerank_query_texts: list[str] | None = None,
    ignore_front_fraction: float = 0.0,
    ignore_back_fraction: float = 0.0,
    chunk_rank: int = 0,
    min_numbers: int = 0,
    penalize_edges: bool = False,
    exclude_chunks: set[int] | None = None,
    context_name: str | None = None,
) -> tuple[str | None, int | None, dict | None]:
    """
    Use document embeddings to locate relevant sections for the provided queries.

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        query_texts: Query phrases to search for
        chunk_size: Size of a chunk in characters; falls back to indexed metadata
        score_threshold: Minimum similarity score to consider a match
        chars_before: Number of characters to include before the best matching chunk (default: 2500)
        chars_after: Number of characters to include after the best matching chunk (default: 2500)

    Returns:
        Tuple of (extracted_text, start_char, log_info) or (None, None, None) if not found
    """
    try:
        chunk_metadata = get_chunk_metadata(document_id)
        if not chunk_metadata:
            return None, None

        resolved_chunk_size = chunk_size or chunk_metadata.get("chunk_size", 5000)
        total_characters = chunk_metadata.get("total_characters", 0)
        num_chunks = chunk_metadata.get("num_chunks", 0)

        if num_chunks == 0:
            return None, None

        # No need to get total pages for character-based chunking

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
            chunk_text, _, _ = get_chunk_text(
                file_path, chunk_index, resolved_chunk_size, document_id
            )
            if not chunk_text:
                continue

            # Skip excluded chunks
            if exclude_chunks and chunk_index in exclude_chunks:
                continue

            # Apply "critical mass of numbers" filter if specified
            if min_numbers > 0:
                num_numbers = _count_numbers(chunk_text)
                if num_numbers < min_numbers:
                    # Skip chunks with insufficient numbers (likely not a financial statement)
                    continue

            chunk_embedding = load_chunk_embedding(document_id, chunk_index)

            if not chunk_embedding:
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
                            file_path, chunk_index, resolved_chunk_size, document_id
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
                if penalize_edges:
                    reranked = _penalize_edge_chunks(reranked, search_range)
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
                if penalize_edges:
                    top_chunks = _penalize_edge_chunks(top_chunks, search_range)
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
            if penalize_edges:
                sorted_chunks = _penalize_edge_chunks(sorted_chunks, search_range)

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
            # Calculate character positions
            chunk_start_char = best_chunk_index * resolved_chunk_size
            chunk_end_char = min(chunk_start_char + resolved_chunk_size, total_characters)

            # Add context before and after
            start_extract_char = max(0, chunk_start_char - chars_before)
            end_extract_char = min(total_characters, chunk_end_char + chars_after)

            log_info = {
                "best_chunk_index": best_chunk_index,
                "chunk_start_char": chunk_start_char,
                "chunk_end_char": chunk_end_char - 1,
                "similarity": best_score,
                "start_extract_char": start_extract_char,
                "end_extract_char": end_extract_char - 1,
                "search_range": {"start": search_range.start, "end": search_range.stop - 1},
            }
            if rerank_details is not None:
                log_info["rerank_top_k"] = rerank_top_k
                log_info["rerank_details"] = rerank_details

            f" (rank {chunk_rank + 1})" if chunk_rank > 0 else ""

            # Load full text from cache
            from app.utils.document_indexer import load_full_document_text

            full_text = load_full_document_text(document_id, file_path)
            extracted_text = full_text[start_extract_char:end_extract_char]

            return extracted_text, start_extract_char, log_info

        return None, None, None

    except Exception:
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


def find_document_section(*args, **kwargs):
    """
    Legacy wrapper for _find_document_section_legacy.
    This ensures backward compatibility for code that still uses semantic search.
    """
    return _find_document_section_legacy(*args, **kwargs)


def find_top_numeric_chunks(
    document_id: str,
    file_path: str,
    top_k: int = 5,
    chunk_size: int | None = None,
    context_name: str | None = None,
) -> list[int]:
    """
    Find the chunks with the highest density of numbers.
    Returns a list of chunk indices sorted by number count descending.
    """
    chunk_metadata = get_chunk_metadata(document_id)
    if not chunk_metadata:
        return []

    resolved_chunk_size = chunk_size or chunk_metadata.get("chunk_size", 2)
    num_chunks = chunk_metadata.get("num_chunks", 0)

    if num_chunks == 0:
        return []

    chunk_counts = []

    # Iterate all chunks
    for chunk_index in range(num_chunks):
        chunk_text, _, _ = get_chunk_text(file_path, chunk_index, resolved_chunk_size, document_id)
        if not chunk_text:
            continue

        count = _count_numbers(chunk_text)
        chunk_counts.append({"chunk_index": chunk_index, "count": count})

    # Sort by count descending
    chunk_counts.sort(key=lambda x: x["count"], reverse=True)

    # Return top K indices
    return [item["chunk_index"] for item in chunk_counts[:top_k]]


def rank_chunks_by_query(
    document_id: str,
    file_path: str,
    chunk_indices: list[int],
    query_texts: list[str],
    chunk_size: int | None = None,
    context_name: str | None = None,
) -> list[int]:
    """
    Rank a list of chunk indices by their similarity to query texts.

    Args:
        document_id: Document ID
        file_path: Path to PDF file
        chunk_indices: List of chunk indices to rank
        query_texts: Query phrases to search for
        chunk_size: Number of characters per chunk

    Returns:
        List of chunk indices sorted by query similarity (best first)
    """
    if not chunk_indices:
        return []

    chunk_metadata = get_chunk_metadata(document_id)
    if not chunk_metadata:
        return chunk_indices

    resolved_chunk_size = chunk_size or chunk_metadata.get("chunk_size", 5000)

    # Generate query embeddings for all query texts
    query_embeddings = [
        generate_embedding_safe(query_text, max_chars=20000, task_type="retrieval_query")
        for query_text in query_texts
    ]

    # Calculate similarity scores for each chunk
    chunk_scores = []
    for chunk_index in chunk_indices:
        # Load or generate chunk embedding
        chunk_embedding = load_chunk_embedding(document_id, chunk_index)

        if not chunk_embedding:
            # Generate embedding if not found
            chunk_text, _, _ = get_chunk_text(
                file_path, chunk_index, resolved_chunk_size, document_id
            )
            chunk_embedding = generate_embedding_safe(
                chunk_text[:20000], max_chars=20000, task_type="retrieval_document"
            )
            save_chunk_embedding(chunk_embedding, document_id, chunk_index)

        # Calculate max similarity across all query embeddings
        max_similarity = max(
            cosine_similarity(chunk_embedding, query_embedding)
            for query_embedding in query_embeddings
        )

        chunk_scores.append({"chunk_index": chunk_index, "similarity": max_similarity})

    # Sort by similarity descending
    chunk_scores.sort(key=lambda x: x["similarity"], reverse=True)

    return [item["chunk_index"] for item in chunk_scores]


def get_chunk_with_context(
    document_id: str,
    file_path: str,
    chunk_index: int,
    chars_before: int = 2500,
    chars_after: int = 2500,
    chunk_size: int | None = None,
) -> tuple[str, int, dict]:
    """
    Get text for a specific chunk including context characters.
    Returns (extracted_text, start_char, log_info)
    """
    chunk_metadata = get_chunk_metadata(document_id)
    if not chunk_metadata:
        return "", 0, {}

    resolved_chunk_size = chunk_size or chunk_metadata.get("chunk_size", 5000)
    total_characters = chunk_metadata.get("total_characters", 0)

    # Calculate character positions
    chunk_start_char = chunk_index * resolved_chunk_size
    chunk_end_char = min(chunk_start_char + resolved_chunk_size, total_characters)

    # Add context before and after
    start_extract_char = max(0, chunk_start_char - chars_before)
    end_extract_char = min(total_characters, chunk_end_char + chars_after)

    # Load full text from cache
    from app.utils.document_indexer import load_full_document_text

    full_text = load_full_document_text(document_id, file_path)

    # Extract the text with context
    extracted_text = full_text[start_extract_char:end_extract_char]

    log_info = {
        "best_chunk_index": chunk_index,
        "chunk_start_char": chunk_start_char,
        "chunk_end_char": chunk_end_char - 1,
        "start_extract_char": start_extract_char,
        "end_extract_char": end_extract_char - 1,
    }

    return extracted_text, start_extract_char, log_info
