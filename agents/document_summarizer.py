"""
Document summarization agent using Gemini LLM
"""

from app.utils.gemini_client import generate_content_safe


def generate_document_summary(text: str) -> str | None:
    """
    Generate a short summary of the document using Gemini LLM.

    Args:
        text: Extracted text from the document (can be full document or first few pages)

    Returns:
        A short summary string (2-3 sentences) or None if generation fails
    """

    # Limit text to first 10000 characters for efficiency
    text_preview = text[:10000]

    prompt = f"""Provide a concise summary of the following document in 2-3 sentences.
Focus on the key information, main points, and important details.

Document text:
{text_preview}

Summary:"""

    try:
        # Note: generate_content_safe doesn't support max_output_tokens yet
        # For now, we'll use the safe wrapper and let the model handle length
        summary = generate_content_safe(prompt)

        # Clean up the summary - remove any markdown formatting
        if summary.startswith("**") or summary.startswith("#"):
            # Remove markdown headers/bold
            summary = summary.lstrip("#*").strip()

        return summary

    except Exception as e:
        # If summary generation fails, return None (non-blocking)
        print(f"Warning: Failed to generate document summary: {str(e)}")
        return None
