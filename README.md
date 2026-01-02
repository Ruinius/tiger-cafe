# Tiger-Cafe

**A private project for Tiger and his friends to play with AI agents performing financial analysis.**

Tiger-Cafe is an AI agent system for analyzing equity investments. This is a personal project where Tiger and his friends experiment with intelligent agents that can research, analyze, and provide insights on equity investments.

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
├── app/             # FastAPI application
│   ├── models/      # SQLAlchemy database models
│   ├── schemas/     # Pydantic schemas for API validation
│   ├── routers/     # API route handlers
│   └── utils/       # Application utilities
├── agents/          # AI agent implementations
├── frontend/        # React frontend application
│   ├── src/         # Source files
│   │   ├── components/  # React components
│   │   ├── pages/       # Page components
│   │   └── contexts/    # React contexts
│   └── package.json    # Frontend dependencies
├── data/            # Data storage and cache
│   ├── cache/       # Cached data
│   ├── storage/     # Persistent storage
│   └── uploads/     # Uploaded PDF files
├── utils/           # Utility functions and helpers
├── config/          # Configuration files
├── tests/           # Test suite
├── docs/            # Documentation
├── requirements.txt # Python dependencies
└── run.py           # Application entry point
```

## Setup

### Backend Setup

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

4. Set up environment variables:
Create a `.env` file in the project root with:
```
GEMINI_API_KEY=your-gemini-api-key-here
GOOGLE_CLIENT_ID=your-google-client-id-here
GOOGLE_CLIENT_SECRET=your-google-client-secret-here
```

5. Run database migration (if needed):
```bash
python migrate_add_unique_id.py
```

6. Start the backend server:
```bash
python run.py
```

The API will be available at http://localhost:8000

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Set up environment variables:
Create a `.env` file in the `frontend` directory:
```
VITE_GOOGLE_CLIENT_ID=your-google-client-id-here
```

4. Start the development server:
```bash
npm run dev
```

The frontend will be available at http://localhost:3000

## User Journey Overview

Tiger-Cafe provides three main user journey epics:

1. **Document Upload and Classification**: Users upload PDFs (earnings reports, filings, analyst reports), and the system automatically classifies, deduplicates, and indexes them.

2. **Company Document Management**: Users browse companies, view document libraries with processing status, and trigger financial analysis on selected documents.

3. **Financial Analysis and Valuation**: Users view financial metrics, interact with valuation models, review sensitivity analysis, and read LLM-generated summaries.

For detailed planning and user journey specifications, see [docs/PLANNING.md](docs/PLANNING.md).

## Development

This project is in active development. Stay tuned for updates!

## Clarifications and Planning Notes

### Document Size Limitations (Future Enhancement)

**Current Limitation:**
The document indexer currently truncates text to 20,000 characters for embedding generation. This means only the first portion of very large documents (e.g., 500-page annual reports) will be searchable. PDF extraction can handle unlimited pages, but processing may be slow for very large documents.

**Future Enhancement:**
- Implement chunk-based indexing for large documents (split into multiple embeddings)
- Increase embedding character limit if Gemini API allows
- Add page-based extraction limits to prevent memory issues
- Consider implementing document summarization for sections beyond the indexed portion

<!-- Add any clarifications, decisions, or notes about user journeys, features, or architecture here -->

## License

[To be determined]

