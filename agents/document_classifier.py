"""
Document classification agent using Gemini LLM
"""

from app.models.document import DocumentType
from app.utils.gemini_client import generate_content_safe
from app.utils.llm_parsing import parse_json_response


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
    "document_type": one of ["earnings_announcement", "quarterly_filing", "annual_filing", "press_release", "analyst_report", "news_article", "other"],
    "time_period": the time period in format like "Q3 2024", "FY 2023", "2024-Q1", or null if not found,
    "company_name": the company name or null if not found,
    "ticker": the stock ticker symbol or null if not found,
    "confidence": one of ["high", "medium", "low"] based on how confident you are in the classification
}}

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

    fallback = {
        "document_type": None,
        "time_period": None,
        "company_name": None,
        "ticker": None,
        "confidence": "low",
    }

    try:
        response_text = generate_content_safe(prompt)
    except Exception as e:
        print(f"Error generating classification response: {str(e)}")
        return fallback

    result = parse_json_response(
        response_text,
        fallback=fallback,
        required_keys=["document_type", "confidence"],
    )

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
                "other": DocumentType.OTHER,
            }
            result["document_type"] = doc_type_map.get(
                result["document_type"], DocumentType.OTHER
            )
        except Exception:
            result["document_type"] = None

    return result
