"""
Mock responses for LLM calls during testing.
"""

MOCK_EMBEDDING_RESPONSE = [0.1] * 768

# Mock JSON response for a financial document extraction
MOCK_EXTRACTION_RESPONSE = """
{
  "company_name": "Test Company Inc.",
  "period": "Q3 2023",
  "currency": "USD",
  "financial_statements": {
    "balance_sheet": {
      "assets": [
        {"name": "Cash and Cash Equivalents", "value": 1000000, "category": "Current Assets"},
        {"name": "Accounts Receivable", "value": 500000, "category": "Current Assets"},
        {"name": "Property, Plant and Equipment", "value": 2000000, "category": "Non-Current Assets"}
      ],
      "liabilities": [
        {"name": "Accounts Payable", "value": 300000, "category": "Current Liabilities"},
        {"name": "Long-term Debt", "value": 1000000, "category": "Non-Current Liabilities"}
      ],
      "equity": [
        {"name": "Common Stock", "value": 100000, "category": "Equity"},
        {"name": "Retained Earnings", "value": 2100000, "category": "Equity"}
      ]
    },
    "income_statement": {
      "revenue": [
        {"name": "Sales Revenue", "value": 5000000}
      ],
      "expenses": [
        {"name": "Cost of Goods Sold", "value": 3000000},
        {"name": "Operating Expenses", "value": 1000000}
      ]
    },
    "cash_flow": {
      "operating": [],
      "investing": [],
      "financing": []
    }
  }
}
"""

def get_mock_response(prompt: str) -> str:
    """Return a mock response based on the prompt content."""
    prompt_lower = prompt.lower()

    # Check for keywords to determine which mock response to return
    if "extract" in prompt_lower and "json" in prompt_lower:
        return MOCK_EXTRACTION_RESPONSE
    elif "summarize" in prompt_lower:
        return "This is a mock summary of the document."
    elif "identify" in prompt_lower:
         return "Mock Identification: This looks like a 10-K."

    # Default fallback
    return '{"mock_response": "default", "content": "This is a default mock response."}'
