# Tiger-Cafe

An AI agent system for analyzing equity investments. Tiger-Cafe provides intelligent agents that can research, analyze, and provide insights on equity investments.

## Project Overview

Tiger-Cafe is a web application designed to help with equity investment analysis through AI-powered agents. The system provides a user-friendly interface for document management and financial analysis, with intelligent agents capable of:
- Document classification and indexing (earnings reports, filings, analyst reports)
- Financial data parsing and extraction
- Financial statement adjustments based on principles in Tim Koller's Valuation
- Organic growth, operating margin, and capital turnover assessment
- Intrinsic value calculations based on principles in Tim Koller's Valuation
- Market belief and sensitivity analysis
- Interactive valuation models and LLM-driven insights

## Project Structure

```
tiger-cafe/
├── agents/          # AI agent implementations
├── data/            # Data storage and cache
├── utils/           # Utility functions and helpers
├── config/          # Configuration files
├── tests/           # Test suite
├── docs/            # Documentation
└── requirements.txt # Python dependencies
```

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd tiger-cafe
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## User Journey Overview

Tiger-Cafe provides three main user journey epics:

1. **Document Upload and Classification**: Users upload PDFs (earnings reports, filings, analyst reports), and the system automatically classifies, deduplicates, and indexes them.

2. **Company Document Management**: Users browse companies, view document libraries with processing status, and trigger financial analysis on selected documents.

3. **Financial Analysis and Valuation**: Users view financial metrics, interact with valuation models, review sensitivity analysis, and read LLM-generated summaries.

For detailed planning and user journey specifications, see [docs/PLANNING.md](docs/PLANNING.md).

## Development

This project is in active development. Stay tuned for updates!

## Clarifications and Planning Notes

<!-- Add any clarifications, decisions, or notes about user journeys, features, or architecture here -->

## License

[To be determined]

