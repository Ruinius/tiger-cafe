"""
Document indexing with Gemini embeddings
"""

import google.generativeai as genai
from config.config import GEMINI_API_KEY, EMBEDDING_MODEL
from typing import List, Optional
import os
import json


# Initialize Gemini
genai.configure(api_key=GEMINI_API_KEY)


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
        # Truncate text if it's too long to avoid API errors and improve performance
        if len(text) > max_chars:
            # Use first portion of text (most important content is usually at the beginning)
            text = text[:max_chars]
            print(f"Warning: Text truncated to {max_chars} characters for embedding generation")
        
        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=text,
            task_type="retrieval_document"
        )
        return result['embedding']
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
    Load embedding from disk.
    
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

