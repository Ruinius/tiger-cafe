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

5. Initialize database:
The database schema will be automatically created from models when the application starts. For a fresh database or to reset, you can run:
```bash
python migrate_baseline_schema.py
```

6. Set up pre-commit hooks (recommended):
```bash
# Install pre-commit (if not already installed)
pip install pre-commit

# Install git hooks
uv run pre-commit install

# Or if uv is not available:
pre-commit install
```

7. Start the backend server:
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
- LLM-based line-by-line extraction with currency and unit detection
- Unit support: Extracts and displays units (ones, thousands, millions, billions, or ten_thousands) for balance sheets, income statements, and additional items
- Comprehensive validation:
  - Balance sheet: Current assets, total assets, current liabilities, total liabilities sum verification, balance sheet equation validation
  - Income statement: Gross profit, operating income, and net income calculation verification
  - Retry logic (up to 3 attempts) for failed extractions
- Operating/non-operating classification for each line item (authoritative lookup table with LLM fallback)
- Additional items extraction: Prior period revenue, YOY revenue growth, amortization, basic shares outstanding, diluted shares outstanding (each with unit fields)
- Historical calculations: Automatic calculation and display of Net Working Capital, Invested Capital, EBITA, and other key metrics with unit support
  - Capital Turnover is annualized for quarterly statements (Q1-Q4) by multiplying revenue by 4
- Real-time progress tracking with 5 milestones:
  - Extracting balance sheet, Classifying balance sheet
  - Extracting income statement, Extracting additional items, Classifying income statement
- Re-run and delete functionality for financial statements

For detailed planning and user journey specifications, see [docs/PLANNING.md](docs/PLANNING.md).

## Development

### Development Tools

**Pre-commit Hooks:**
This project uses pre-commit hooks to ensure code quality and security:

**Installed Hooks:**
- **detect-secrets** - Scans for API keys, tokens, passwords
- **gitleaks** - Additional secret/credential detection
- **detect-private-key** - Catches private key files
- **bandit** - Python security linter
- **ruff** - Fast Python linter + formatter
- **check-added-large-files** - Prevents large file commits
- **check-merge-conflict** - Catches unresolved merge conflicts

**Setup:**
```bash
# Install hooks (run once after cloning)
uv run pre-commit install

# Run all hooks manually on all files
uv run pre-commit run --all-files
```

Hooks will automatically run on `git commit`. The project uses `uv` for running pre-commit (see `requirements.txt`), which helps with environment consistency.

### Database Migrations

**Current Setup:**
- **Baseline Migration**: `migrate_baseline_schema.py` - Creates all tables from SQLAlchemy models
- **Old Migrations**: Archived in `migrations_archive/` for reference

**For Development:**
- Schema is automatically created from models when the app starts (`app/main.py`)
- Use `migrate_baseline_schema.py` to initialize or reset the database

**For Future Production:**
- Baseline migration represents current schema state
- Future schema changes will use new incremental migrations

See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for details.

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

