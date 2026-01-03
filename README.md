# Tiger-Cafe

**A private project for Tiger and his friends to play with AI agents performing financial analysis.**

Tiger-Cafe is an AI agent system for analyzing equity investments. This is a personal project where Tiger and his friends experiment with intelligent agents that can research, analyze, and provide insights on equity investments.

## Project Overview

Tiger-Cafe is a web application designed to help with equity investment analysis through AI-powered agents. The system provides a user-friendly interface for document management and financial analysis, with intelligent agents capable of:
- Document classification and indexing (earnings reports, filings, analyst reports)
- Financial data parsing and extraction
- Balance sheet extraction and validation with operating/non-operating classification
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

## Current Features

### Document Management
- Multi-file drag-and-drop upload (up to 10 files)
- Automatic document classification (earnings announcements, quarterly/annual filings, press releases, etc.)
- Content-based duplicate detection
- Real-time upload progress tracking with milestones
- Chunk-based document indexing with Gemini embeddings (5-page chunks, persisted for reuse)
- Priority-based processing queue (classification/indexing prioritized over financial statement extraction)

### Financial Statement Processing (Phase 5.1 & 5.2 - Complete)
- Automatic balance sheet and income statement extraction from earnings announcements, quarterly filings, and annual reports
- Chunk-based embedding search using persisted 5-page chunk embeddings
- LLM-based line-by-line extraction with currency detection
- Comprehensive validation:
  - Balance sheet: Current assets, total assets, current liabilities, total liabilities sum verification, balance sheet equation validation
  - Income statement: Gross profit, operating income, and net income calculation verification
  - Retry logic (up to 3 attempts) for failed extractions
- Operating/non-operating classification for each line item (authoritative lookup table with LLM fallback)
- Additional items extraction: Prior period revenue, YOY revenue growth, amortization, basic shares outstanding, diluted shares outstanding
- Real-time progress tracking with 5 milestones:
  - Extracting balance sheet, Classifying balance sheet
  - Extracting income statement, Extracting additional items, Classifying income statement
- Re-run and delete functionality for financial statements

For detailed planning and user journey specifications, see [docs/PLANNING.md](docs/PLANNING.md).

## Development

This project is in active development. Stay tuned for updates!

## Clarifications and Planning Notes

### Chunk-Based Document Indexing

**Current Implementation:**
- Documents are split into 5-page chunks for embedding generation
- Each chunk embedding is persisted to disk and reused during extraction
- Eliminates duplicate API calls when re-running extractions
- Provides more granular search capabilities than document-level embeddings
- Large documents are fully indexed across all chunks

**Benefits:**
- Performance: Chunk embeddings generated once during indexing, reused during extraction
- Efficiency: No duplicate embedding generation when re-running extractions
- Precision: 5-page chunks provide better search precision than document-level embeddings

<!-- Add any clarifications, decisions, or notes about user journeys, features, or architecture here -->

## License

[To be determined]

