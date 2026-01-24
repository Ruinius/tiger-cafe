"""
Document indexing with Gemini embeddings
"""

import glob
import json
import logging
import os

import pdfplumber

from app.utils.gemini_client import generate_embedding_safe

# Suppress pdfminer FontBBox warnings
logging.getLogger("pdfminer").setLevel(logging.ERROR)


def save_chunk_embedding(
    embedding: list[float], document_id: str, chunk_index: int, storage_dir: str = "data/storage"
) -> str:
    """
    Save chunk embedding to disk.

    Args:
        embedding: Embedding vector
        document_id: Document ID
        chunk_index: Index of the chunk (0-based)
        storage_dir: Directory to save embeddings

    Returns:
        Path to saved embedding file
    """
    os.makedirs(storage_dir, exist_ok=True)

    embedding_path = os.path.join(storage_dir, f"{document_id}_chunk_{chunk_index}_embedding.json")

    with open(embedding_path, "w") as f:
        json.dump(embedding, f)

    return embedding_path


def load_chunk_embedding(
    document_id: str, chunk_index: int, storage_dir: str = "data/storage"
) -> list[float] | None:
    """
    Load chunk embedding from disk.

    Args:
        document_id: Document ID
        chunk_index: Index of the chunk (0-based)
        storage_dir: Directory where embeddings are stored

    Returns:
        Embedding vector or None if not found
    """
    embedding_path = os.path.join(storage_dir, f"{document_id}_chunk_{chunk_index}_embedding.json")

    if not os.path.exists(embedding_path):
        return None

    with open(embedding_path) as f:
        return json.load(f)


def get_chunk_metadata(document_id: str, storage_dir: str = "data/storage") -> dict | None:
    """
    Load chunk metadata (number of chunks, chunk size, etc.).

    Args:
        document_id: Document ID
        storage_dir: Directory where metadata is stored

    Returns:
        Dictionary with chunk metadata or None if not found
    """
    metadata_path = os.path.join(storage_dir, f"{document_id}_chunks_metadata.json")

    if not os.path.exists(metadata_path):
        return None

    with open(metadata_path) as f:
        return json.load(f)


def save_chunk_metadata(metadata: dict, document_id: str, storage_dir: str = "data/storage") -> str:
    """
    Save chunk metadata to disk.

    Args:
        metadata: Dictionary with chunk metadata (num_chunks, chunk_size, total_pages)
        document_id: Document ID
        storage_dir: Directory to save metadata

    Returns:
        Path to saved metadata file
    """
    os.makedirs(storage_dir, exist_ok=True)

    metadata_path = os.path.join(storage_dir, f"{document_id}_chunks_metadata.json")

    with open(metadata_path, "w") as f:
        json.dump(metadata, f)

    return metadata_path


def delete_chunk_embeddings(document_id: str, storage_dir: str = "data/storage") -> None:
    """
    Delete all chunk embeddings and metadata for a document.

    Args:
        document_id: Document ID
        storage_dir: Directory where embeddings are stored
    """
    chunk_pattern = os.path.join(storage_dir, f"{document_id}_chunk_*_embedding.json")
    for chunk_path in glob.glob(chunk_pattern):
        try:
            os.remove(chunk_path)
        except OSError:
            pass

    metadata_path = os.path.join(storage_dir, f"{document_id}_chunks_metadata.json")
    if os.path.exists(metadata_path):
        try:
            os.remove(metadata_path)
        except OSError:
            pass


def _extract_page_range_text(file_path: str, start_page: int, end_page: int) -> str:
    """
    Extract text from a specific page range in a PDF file.

    Args:
        file_path: Path to PDF file
        start_page: Starting page index (0-based, inclusive)
        end_page: Ending page index (0-based, exclusive)

    Returns:
        Extracted text from the page range
    """
    import logging

    logging.getLogger("pdfminer").setLevel(logging.ERROR)

    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        total_pages = len(pdf.pages)
        clamped_start = max(0, min(start_page, total_pages))
        clamped_end = max(clamped_start, min(end_page, total_pages))

        for page_index in range(clamped_start, clamped_end):
            try:
                page_text = pdf.pages[page_index].extract_text()
                if page_text:
                    text_parts.append(page_text)
            except Exception as e:
                print(f"Warning: Failed to extract text from page {page_index} in {file_path}: {e}")
                continue
    return "\n\n".join(text_parts)


def load_full_document_text(
    document_id: str, file_path: str, storage_dir: str = "data/storage"
) -> str:
    """
    Load the full document text from disk cache, or extract from PDF if not cached.

    Args:
        document_id: Document ID
        file_path: Path to PDF file (used as fallback)
        storage_dir: Directory where full text is stored

    Returns:
        Full document text
    """
    import logging

    # Try to load from disk first
    full_text_path = os.path.join(storage_dir, f"{document_id}_full_text.txt")

    if os.path.exists(full_text_path):
        try:
            with open(full_text_path, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Failed to load cached text from {full_text_path}: {e}")
            print("Falling back to PDF extraction")

    # Fallback: extract from PDF
    logging.getLogger("pdfminer").setLevel(logging.ERROR)

    full_text_parts = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page_idx in range(len(pdf.pages)):
                try:
                    page_text = pdf.pages[page_idx].extract_text()
                    if page_text:
                        full_text_parts.append(page_text)
                except Exception as e:
                    print(f"Warning: Failed to extract text from page {page_idx}: {e}")
                    continue

        full_text = "\n\n".join(full_text_parts)

        # Cache the text for future use
        try:
            os.makedirs(storage_dir, exist_ok=True)
            with open(full_text_path, "w", encoding="utf-8") as f:
                f.write(full_text)
            print(f"Cached full document text to {full_text_path}")
        except Exception as e:
            print(f"Warning: Failed to cache full text: {e}")

        return full_text

    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""


def index_document_chunks(
    file_path: str, document_id: str, chunk_size: int = 5000, storage_dir: str = "data/storage"
) -> dict:
    """
    Index a document by creating embeddings for character-based chunks.
    This replaces the old page-based chunking approach.

    Args:
        file_path: Path to PDF file
        document_id: Document ID
        chunk_size: Number of characters per chunk (default: 5000)
        storage_dir: Directory to save chunk embeddings

    Returns:
        Dictionary with indexing results:
        {
            "num_chunks": number of chunks created,
            "total_pages": total pages in document,
            "chunk_size": characters per chunk,
            "total_characters": total characters in document
        }
    """
    import logging

    # Suppress noisy pdfminer logs
    logging.getLogger("pdfminer").setLevel(logging.ERROR)

    try:
        failed_pages = []  # Track which pages failed

        # Open PDF once for the entire operation
        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)

            # Extract all text from the document first
            full_text_parts = []
            for page_idx in range(total_pages):
                try:
                    page_text = pdf.pages[page_idx].extract_text()
                    if page_text:
                        full_text_parts.append(page_text)
                except Exception as e:
                    failed_pages.append(page_idx + 1)  # 1-indexed for user display
                    print(
                        f"ERROR: Failed to extract text from page {page_idx + 1} of {document_id}: {e}"
                    )
                    # Continue to next page rather than failing the whole process
                    continue

            full_text = "\n\n".join(full_text_parts)
            total_characters = len(full_text)

            # Calculate number of chunks based on character count
            num_chunks = (total_characters + chunk_size - 1) // chunk_size  # Ceiling division

            print(
                f"Indexing document {document_id}: {total_pages} pages, {total_characters} characters, "
                f"{num_chunks} chunks of {chunk_size} characters each"
            )

            # Log to UI
            from app.utils.financial_statement_progress import FinancialStatementMilestone, add_log

            add_log(
                document_id,
                FinancialStatementMilestone.INDEX,
                f"Starting indexing: {num_chunks} chunks from {total_pages} pages",
            )

            # Save full text to disk for fast retrieval
            import os

            os.makedirs(storage_dir, exist_ok=True)
            full_text_path = os.path.join(storage_dir, f"{document_id}_full_text.txt")
            with open(full_text_path, "w", encoding="utf-8") as f:
                f.write(full_text)
            print(f"Saved full document text to {full_text_path}")

            # Generate embeddings for each chunk
            for chunk_index in range(num_chunks):
                start_char = chunk_index * chunk_size
                end_char = min(start_char + chunk_size, total_characters)

                # Check if chunk embedding already exists
                existing_embedding = load_chunk_embedding(document_id, chunk_index, storage_dir)
                if existing_embedding:
                    # print(f"Chunk {chunk_index} embedding already exists, skipping")
                    continue

                # Extract text for this chunk
                chunk_text = full_text[start_char:end_char]

                # Generate embedding for chunk (limit to 20k chars)
                chunk_embedding = generate_embedding_safe(
                    chunk_text[:20000], max_chars=20000, task_type="retrieval_document"
                )

                # Save chunk embedding
                save_chunk_embedding(chunk_embedding, document_id, chunk_index, storage_dir)
                # print(
                #     f"Generated and saved embedding for chunk {chunk_index} (chars {start_char}-{end_char - 1})"
                # )

        # Check if too many pages failed
        failure_rate = len(failed_pages) / total_pages if total_pages > 0 else 0

        if failed_pages:
            print(
                f"WARNING: {len(failed_pages)} of {total_pages} pages failed extraction ({failure_rate:.1%})"
            )
            print(f"Failed pages: {failed_pages}")

        # If more than 20% of pages failed, raise an error
        if failure_rate > 0.20:
            raise Exception(
                f"Document indexing failed: {len(failed_pages)} of {total_pages} pages "
                f"({failure_rate:.1%}) could not be extracted. Failed pages: {failed_pages}. "
                f"This document may have corrupted fonts or encoding issues."
            )

        # Save metadata
        metadata = {
            "num_chunks": num_chunks,
            "total_pages": total_pages,
            "chunk_size": chunk_size,
            "total_characters": total_characters,
            "failed_pages": failed_pages,
            "failure_rate": failure_rate,
            "full_text_path": full_text_path,
        }
        save_chunk_metadata(metadata, document_id, storage_dir)

        return metadata

    except Exception as e:
        raise Exception(f"Error indexing document chunks: {str(e)}")


def get_chunk_text(
    file_path: str,
    chunk_index: int,
    chunk_size: int = 5000,
    document_id: str | None = None,
    storage_dir: str = "data/storage",
) -> tuple[str, int, int]:
    """
    Get text for a specific chunk.

    Args:
        file_path: Path to PDF file
        chunk_index: Index of the chunk (0-based)
        chunk_size: Number of characters per chunk
        document_id: Document ID (optional, for loading cached text)
        storage_dir: Directory where cached text is stored

    Returns:
        Tuple of (chunk_text, start_char, end_char)
    """
    # Load full text from cache if document_id is provided
    if document_id:
        full_text = load_full_document_text(document_id, file_path, storage_dir)
    else:
        # Fallback: extract from PDF
        import logging

        import pdfplumber

        logging.getLogger("pdfminer").setLevel(logging.ERROR)

        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)
            full_text_parts = []
            for page_idx in range(total_pages):
                try:
                    page_text = pdf.pages[page_idx].extract_text()
                    if page_text:
                        full_text_parts.append(page_text)
                except Exception:
                    continue

        full_text = "\n\n".join(full_text_parts)

    total_characters = len(full_text)

    # Calculate character range for this chunk
    start_char = chunk_index * chunk_size
    end_char = min(start_char + chunk_size, total_characters)

    # Extract text for this chunk
    chunk_text = full_text[start_char:end_char]

    return chunk_text, start_char, end_char
