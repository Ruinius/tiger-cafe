"""
Helpers for combining document section search results.
"""

from __future__ import annotations

from app.utils.document_section_finder import find_document_section


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
