"""
Utilities for finding relevant document sections.
"""

from __future__ import annotations

import re

from app.utils.document_indexer import (
    get_chunk_metadata,
    get_chunk_text,
    load_full_document_text,
)


def _count_numbers(text: str) -> int:
    """Count occurrences of numerical values in text."""
    if not text:
        return 0
    # Match numbers like 1,234.56, (123), -456.0, etc.
    number_pattern = r"\(?\b\d+(?:,\d+)*(?:\.\d+)?\)?\b"
    matches = re.findall(number_pattern, text)
    return len(matches)


def extract_context_around_keywords(
    text: str,
    keywords: list[str],
    context_chars: int = 250,
) -> str:
    """
    Return merged keyword-context snippets from a full document text string.

    Scans the entire text for every occurrence of each keyword (case-insensitive
    substring match), extracts ±context_chars characters around each hit, merges
    overlapping windows, and joins the resulting snippets with '\\n...\\n'.

    Args:
        text: Full document text to scan
        keywords: List of keyword strings to search for
        context_chars: Characters to include before and after each keyword hit

    Returns:
        Joined snippet string, or empty string if no keywords are found
    """
    text_lower = text.lower()
    ranges = []

    for keyword in keywords:
        keyword_lower = keyword.lower()
        start = 0
        while True:
            idx = text_lower.find(keyword_lower, start)
            if idx == -1:
                break

            range_start = max(0, idx - context_chars)
            range_end = min(len(text), idx + len(keyword_lower) + context_chars)
            ranges.append((range_start, range_end))

            start = idx + len(keyword_lower)

    if not ranges:
        return ""

    # Sort and merge overlapping ranges
    ranges.sort(key=lambda x: x[0])
    merged: list[tuple[int, int]] = []
    current_start, current_end = ranges[0]
    for next_start, next_end in ranges[1:]:
        if next_start <= current_end:
            current_end = max(current_end, next_end)
        else:
            merged.append((current_start, current_end))
            current_start, current_end = next_start, next_end
    merged.append((current_start, current_end))

    snippets = [text[s:e] for s, e in merged]
    return "\n...\n".join(snippets)


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

    for chunk_index in range(num_chunks):
        chunk_text, _, _ = get_chunk_text(file_path, chunk_index, resolved_chunk_size, document_id)
        if not chunk_text:
            continue

        count = _count_numbers(chunk_text)
        chunk_counts.append({"chunk_index": chunk_index, "count": count})

    chunk_counts.sort(key=lambda x: x["count"], reverse=True)

    return [item["chunk_index"] for item in chunk_counts[:top_k]]


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

    full_text = load_full_document_text(document_id, file_path)

    extracted_text = full_text[start_extract_char:end_extract_char]

    log_info = {
        "best_chunk_index": chunk_index,
        "chunk_start_char": chunk_start_char,
        "chunk_end_char": chunk_end_char - 1,
        "start_extract_char": start_extract_char,
        "end_extract_char": end_extract_char - 1,
    }

    return extracted_text, start_extract_char, log_info
