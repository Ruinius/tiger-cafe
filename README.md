# Tiger-Cafe

**A private project for Tiger and his friends to play with AI agents performing financial analysis.**

Tiger-Cafe is a web application that pairs AI agents with a document workflow to analyze equity investments. It focuses on ingesting financial documents, extracting structured statements, and presenting valuation-ready outputs grounded in Tim Koller's *Valuation* methodology.

## At a Glance

- **Document intake + classification** for earnings reports, filings, analyst reports, and more.
- **Financial statement extraction** with validation, operating/non-operating classification, and unit handling.
- **AI-assisted analysis** for intrinsic value, sensitivity, and market belief exploration.
- **Collaborative workflow** with shared dashboard and attribution tracking.

## Quickstart

### Backend

```bash
git clone <repository-url>
cd tiger-cafe

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

# Configure environment variables
cp keys.example.txt .env
# Edit .env with your keys

# (Optional) initialize a fresh database
python migrate_baseline_schema.py

python run.py
```

The API is available at http://localhost:8000 with docs at http://localhost:8000/docs.

### Frontend

```bash
cd frontend
npm install

# Configure environment variables
# Add VITE_GOOGLE_CLIENT_ID to root .env file (Vite automatically loads VITE_* variables from root)

npm run dev
```

The frontend dev server defaults to http://localhost:3000.

## Configuration

Tiger-Cafe loads configuration from `.env` and `config/config.py`.

**Required environment variables:**

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Gemini API access for LLM + embeddings |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID (backend) |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret (backend) |
| `VITE_GOOGLE_CLIENT_ID` | Google OAuth client ID (frontend - set in root `.env`) |

**Optional environment variables:**

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./tiger_cafe.db` | Database connection string |
| `ENVIRONMENT` | `development` | Environment name |
| `DEBUG` | `true` in dev | Enable development-only endpoints |

Data directories (created automatically if missing):

- `data/cache` – cached artifacts and embeddings
- `data/storage` – persisted data artifacts
- `data/uploads` – uploaded PDFs
- `logs/` – log output (see `logs/tiger-cafe.log`)

## Project Structure

```
tiger-cafe/
├── app/             # FastAPI application
│   ├── models/      # SQLAlchemy models
│   ├── routers/     # API route handlers
│   ├── schemas/     # Pydantic schemas
│   └── utils/       # Extraction + agent utilities
├── agents/          # AI agent implementations
├── frontend/        # React + Vite frontend
├── docs/            # Detailed documentation
├── data/            # Local storage (uploads/cache)
├── config/          # Config defaults and examples
└── run.py           # Application entry point
```

## Development Workflow

### Pre-commit Hooks

```bash
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
Add `VITE_GOOGLE_CLIENT_ID` to the root `.env` file (Vite automatically loads variables prefixed with `VITE_` from the root directory):
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

Hooks include: `detect-secrets`, `gitleaks`, `bandit`, `ruff`, and merge-conflict checks.

### Database Migrations

- Baseline schema is created from SQLAlchemy models via `migrate_baseline_schema.py`.
- Archived historical migrations live in `migrations_archive/`.
- See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for details.

### Helpful Commands

```bash
# Reset database (SQLite)
rm tiger_cafe.db
python migrate_baseline_schema.py

# Run backend directly with uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Documentation Index

- [Setup Guide](docs/SETUP_GUIDE.md)
- [Architecture Overview](docs/ARCHITECTURE.md)
- [Database Schema](docs/DATABASE_SCHEMA.md)
- [Contributing Guide](docs/CONTRIBUTING.md)
- [UI/UX Design](docs/UI_UX_DESIGN.md)
- [Planning Notes](docs/PLANNING.md)

## License

[To be determined]
