"""
Document summarization agent using Gemini LLM
"""

import google.generativeai as genai
from config.config import GEMINI_API_KEY, DEFAULT_MODEL, TEMPERATURE
from typing import Optional


# Initialize Gemini
genai.configure(api_key=GEMINI_API_KEY)


def generate_document_summary(text: str) -> Optional[str]:
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
        model = genai.GenerativeModel(
            model_name=DEFAULT_MODEL,
            generation_config={
                "temperature": TEMPERATURE,
                "max_output_tokens": 200,  # Limit summary length
            }
        )
        
        response = model.generate_content(prompt)
        summary = response.text.strip()
        
        # Clean up the summary - remove any markdown formatting
        if summary.startswith("**") or summary.startswith("#"):
            # Remove markdown headers/bold
            summary = summary.lstrip("#*").strip()
        
        return summary
    
    except Exception as e:
        # If summary generation fails, return None (non-blocking)
        print(f"Warning: Failed to generate document summary: {str(e)}")
        return None

