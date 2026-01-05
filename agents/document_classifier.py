"""
Document classification agent using Gemini LLM
"""

import json

from app.models.document import DocumentType
from app.utils.gemini_client import generate_content_safe


def classify_document(text: str) -> dict[str, str | None]:
    """
    Classify a document using Gemini LLM to determine:
    - Document type (earnings announcement, filing, etc.)
    - Time period (Q3 2024, FY 2023, etc.)
    - Company name and ticker symbol

    Args:
        text: Extracted text from the first few pages of the document

    Returns:
        Dictionary with:
        - document_type: DocumentType enum value or None
        - time_period: String like "Q3 2024" or "FY 2023" or None
        - company_name: Company name or None
        - ticker: Ticker symbol or None
        - confidence: Confidence level (high/medium/low) or None
    """

    prompt = f"""Analyze the following document text and extract key information.
Return a JSON object with the following structure:
{{
    "document_type": one of ["earnings_announcement", "quarterly_filing", "annual_filing", "press_release", "analyst_report", "news_article", "transcript", "other"],
    "time_period": the time period in format like "Q3 2024", "FY 2023", "2024-Q1", or null if not EXPLICITLY found in the document text,
    "company_name": the company name or null if not EXPLICITLY found in the document text,
    "ticker": the stock ticker symbol or null if not EXPLICITLY found in the document text,
    "confidence": one of ["high", "medium", "low"] based on how confident you are in the classification
}}

CRITICAL ANTI-HALLUCINATION RULES:
- ONLY extract information that is EXPLICITLY shown in the document text below
- DO NOT invent, infer, or assume company names, tickers, or time periods
- If information is not visible in the document text, use null
- DO NOT use external knowledge to fill in missing information

IMPORTANT: Document type classification rules:
- "earnings_announcement": Use ONLY for press releases or announcements that specifically report quarterly or annual earnings results, financial performance metrics (revenue, profit, EPS), and earnings guidance. These typically include phrases like "earnings", "revenue", "net income", "EPS", "quarterly results", "annual results", or financial performance data.
- "press_release": Use for all OTHER press releases that are NOT earnings announcements. Examples include: product launches, partnerships, executive appointments, regulatory updates, strategic initiatives, mergers/acquisitions, legal matters, or any other company news that is not primarily about earnings/financial results.
- "quarterly_filing": Official SEC quarterly filings (10-Q forms)
- "annual_filing": Official SEC annual filings (10-K forms)
- "analyst_report": Reports from financial analysts or research firms
- "news_article": Third-party news articles about the company
- "other": Any document that doesn't fit the above categories

When in doubt between "earnings_announcement" and "press_release", choose "earnings_announcement" if the document primarily focuses on financial results, earnings, revenue, or quarterly/annual performance metrics.

Document text (first few pages):
{text[:5000]}  # Limit to first 5000 characters

Return only valid JSON, no additional text."""

    try:
        # Use temperature 0.0 for classification to prevent hallucination
        response_text = generate_content_safe(prompt, temperature=0.0)

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        result = json.loads(response_text)

        # Map document_type string to DocumentType enum
        if result.get("document_type"):
            try:
                doc_type_map = {
                    "earnings_announcement": DocumentType.EARNINGS_ANNOUNCEMENT,
                    "quarterly_filing": DocumentType.QUARTERLY_FILING,
                    "annual_filing": DocumentType.ANNUAL_FILING,
                    "press_release": DocumentType.PRESS_RELEASE,
                    "analyst_report": DocumentType.ANALYST_REPORT,
                    "news_article": DocumentType.NEWS_ARTICLE,
                    "transcript": DocumentType.TRANSCRIPT,
                    "other": DocumentType.OTHER,
                }
                result["document_type"] = doc_type_map.get(
                    result["document_type"], DocumentType.OTHER
                )
            except Exception:
                result["document_type"] = None

        return result

    except json.JSONDecodeError:
        # If JSON parsing fails, return None values
        return {
            "document_type": None,
            "time_period": None,
            "company_name": None,
            "ticker": None,
            "confidence": "low",
        }
    except Exception as e:
        raise Exception(f"Error classifying document: {str(e)}")
