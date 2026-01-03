"""
Document indexing with Gemini embeddings
"""

from config.config import EMBEDDING_MODEL
from app.utils.gemini_client import generate_embedding_safe
from app.utils.pdf_extractor import extract_text_from_pdf
from typing import List, Optional, Dict, Tuple
import os
import json
import pdfplumber


def generate_embedding(text: str, max_chars: int = 20000) -> List[float]:
    """
    Generate embedding for text using Gemini embedding model.
    
    Args:
        text: Text to generate embedding for
        max_chars: Maximum characters to use for embedding (default: 20000)
                   Gemini embedding model has token limits, so we truncate very long text
    
    Returns:
        List of floats representing the embedding vector
    """
    try:
        # Use the safe wrapper which handles truncation, rate limiting, and retries
        return generate_embedding_safe(text, max_chars=max_chars, task_type="retrieval_document")
    except Exception as e:
        raise Exception(f"Error generating embedding: {str(e)}")


def save_embedding(embedding: List[float], document_id: str, storage_dir: str = "data/storage") -> str:
    """
    Save embedding to disk.
    
    Args:
        embedding: Embedding vector
        document_id: Document ID
        storage_dir: Directory to save embeddings
    
    Returns:
        Path to saved embedding file
    """
    os.makedirs(storage_dir, exist_ok=True)
    
    embedding_path = os.path.join(storage_dir, f"{document_id}_embedding.json")
    
    with open(embedding_path, 'w') as f:
        json.dump(embedding, f)
    
    return embedding_path


def load_embedding(document_id: str, storage_dir: str = "data/storage") -> Optional[List[float]]:
    """
    Load document-level embedding from disk (for backward compatibility).
    
    Args:
        document_id: Document ID
        storage_dir: Directory where embeddings are stored
    
    Returns:
        Embedding vector or None if not found
    """
    embedding_path = os.path.join(storage_dir, f"{document_id}_embedding.json")
    
    if not os.path.exists(embedding_path):
        return None
    
    with open(embedding_path, 'r') as f:
        return json.load(f)


def save_chunk_embedding(embedding: List[float], document_id: str, chunk_index: int, storage_dir: str = "data/storage") -> str:
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
    
    with open(embedding_path, 'w') as f:
        json.dump(embedding, f)
    
    return embedding_path


def load_chunk_embedding(document_id: str, chunk_index: int, storage_dir: str = "data/storage") -> Optional[List[float]]:
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
    
    with open(embedding_path, 'r') as f:
        return json.load(f)


def get_chunk_metadata(document_id: str, storage_dir: str = "data/storage") -> Optional[Dict]:
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
    
    with open(metadata_path, 'r') as f:
        return json.load(f)


def save_chunk_metadata(metadata: Dict, document_id: str, storage_dir: str = "data/storage") -> str:
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
    
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f)
    
    return metadata_path


def index_document_chunks(file_path: str, document_id: str, chunk_size: int = 5, storage_dir: str = "data/storage") -> Dict:
    """
    Index a document by creating embeddings for 5-page chunks.
    This replaces the old document-level embedding approach.
    
    Args:
        file_path: Path to PDF file
        document_id: Document ID
        chunk_size: Number of pages per chunk (default: 5)
        storage_dir: Directory to save chunk embeddings
    
    Returns:
        Dictionary with indexing results:
        {
            "num_chunks": number of chunks created,
            "total_pages": total pages in document,
            "chunk_size": pages per chunk
        }
    """
    try:
        # Get total pages
        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)
        
        # Calculate number of chunks
        num_chunks = (total_pages + chunk_size - 1) // chunk_size  # Ceiling division
        
        print(f"Indexing document {document_id}: {total_pages} pages, {num_chunks} chunks of {chunk_size} pages each")
        
        # Generate embeddings for each chunk
        for chunk_index in range(num_chunks):
            start_page = chunk_index * chunk_size
            end_page = min(start_page + chunk_size, total_pages)
            
            # Check if chunk embedding already exists
            existing_embedding = load_chunk_embedding(document_id, chunk_index, storage_dir)
            if existing_embedding:
                print(f"Chunk {chunk_index} embedding already exists, skipping")
                continue
            
            # Extract text for this chunk
            chunk_text, _, _ = extract_text_from_pdf(file_path, max_pages=end_page)
            # Get only the current chunk
            if start_page > 0:
                prev_text, _, _ = extract_text_from_pdf(file_path, max_pages=start_page)
                chunk_text = chunk_text[len(prev_text):]
            
            # Generate embedding for chunk (limit to 20k chars)
            chunk_embedding = generate_embedding_safe(chunk_text[:20000], max_chars=20000, task_type="retrieval_document")
            
            # Save chunk embedding
            save_chunk_embedding(chunk_embedding, document_id, chunk_index, storage_dir)
            print(f"Generated and saved embedding for chunk {chunk_index} (pages {start_page}-{end_page-1})")
        
        # Save metadata
        metadata = {
            "num_chunks": num_chunks,
            "total_pages": total_pages,
            "chunk_size": chunk_size
        }
        save_chunk_metadata(metadata, document_id, storage_dir)
        
        return metadata
    
    except Exception as e:
        raise Exception(f"Error indexing document chunks: {str(e)}")


def get_chunk_text(file_path: str, chunk_index: int, chunk_size: int = 5) -> Tuple[str, int, int]:
    """
    Get text for a specific chunk.
    
    Args:
        file_path: Path to PDF file
        chunk_index: Index of the chunk (0-based)
        chunk_size: Number of pages per chunk
    
    Returns:
        Tuple of (chunk_text, start_page, end_page)
    """
    start_page = chunk_index * chunk_size
    
    # Get total pages first
    with pdfplumber.open(file_path) as pdf:
        total_pages = len(pdf.pages)
    
    end_page = min(start_page + chunk_size, total_pages)
    
    # Extract text for this chunk
    chunk_text, _, _ = extract_text_from_pdf(file_path, max_pages=end_page)
    # Get only the current chunk
    if start_page > 0:
        prev_text, _, _ = extract_text_from_pdf(file_path, max_pages=start_page)
        chunk_text = chunk_text[len(prev_text):]
    
    return chunk_text, start_page, end_page

