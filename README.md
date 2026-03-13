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

1. **Document Upload and Classification**: Users upload PDFs, and the system automatically classifies, deduplicates, and indexes them. Highly resilient ticker identification is achieved via **Ticker Reflection**.

2. **Mission Control & Real-time Monitoring**: The **Mission Control** dashboard provides a high-fidelity **Intelligence Stream**, showing granular logs and "Gemini response" snippets in real-time as documents are processed.

3. **Financial Analysis and Valuation**: Users view standardized financial statements, interact with valuation models, and perform ROIC/DCF analysis.

### Mission Control & Intelligence Stream
- **Real-time Monitoring**: A "Command Center" dashboard featuring the **Intelligence Stream**.
- **Source Differentiation**: Visually identifies logs from **System** (orchestrator), **Gemini** (logic), and **Tiger Transformer** (mapping).
- **Rich AI Logs**: Direct "Gemini response" snippets provide transparency into the AI's extraction logic, confidence levels, and summary generation.
- **Granular Milestones**: Tracks progress across 8 distinct stages (Uploading → Classification → Indexing → BS Extraction → IS Extraction → Additional Items → Non-Operating Mapping → Complete).

### Robust Financial Extraction
- **Stage 1 (Completeness Audit)**: Gemini audits document sections before extraction to confirm they contain complete financial statements, preventing hallucination.
- **Standalone Multi-model Pipeline**: Leverages the [Tiger-Transformer](https://github.com/Ruinius/tiger-transformer) ([HF Weights](https://huggingface.co/Ruinius/tiger-transformer)) for standardized financial mapping.
- **Ticker Reflection**: Specialized context gathering around exchange names (NASDAQ/NYSE) ensures 100% accurate ticker identification even from microscopic headers.
- **Standardization (Tiger-Transformer)**: Raw line items are mapped to a unified taxonomy using a local **FinnBERT** model for consistent operating vs non-operating classification.
- **Stage 2 (Validation & Self-Correction)**: Automatic mathematical validation of subtotals/totals. If imbalance is detected, the system sends exact error feedback to Gemini for a "Precise Extraction" retry.
- **Support**: High-fidelity extraction for **Earnings Announcements**, with classification-only support for 10-K, 10-Q, and other filing types.

### Financial Modeling & Valuation (Phase 8)
- **DCF (Discounted Cash Flow) Model** with customizable assumptions:
  - 3-stage revenue growth (Years 1-5, 6-10, Terminal)
  - 3-stage EBITA margin projections
  - 3-stage marginal capital turnover
  - Operating tax rate and WACC inputs
- **Intrinsic Value Calculation**:
  - 10-year cash flow projections
  - Terminal value using Value Driver Formula
  - Mid-year convention for discounting
  - Present value calculations
- **Company-Level Historical Analysis**:
  - Comprehensive historical metrics table
  - Statistical analysis (averages, medians)
  - YOY marginal capital turnover
  - Custom ROIC formatting

### Frontend Architecture (Phase 13: View-Based 2.0)
- **View-Based Architecture**:
  - Application state driven by `viewState` (`GLOBAL`, `COMPANY`, `DOCUMENT`)
  - **Dashboard Orchestrator**: Single source of truth for navigation and layout
  - **Monolith Elimination**: `LeftPanel` and `RightPanel` replaced by dedicated Views
- **Business Logic Layer**:
  - All logic extracted to custom hooks (`useDashboardData`, `useDocumentData`, `usePdfViewer`)
  - Views are purely presentational components
- **Modern Directory Structure**:
  - `components/views/`: Domain-specific views (`global`, `company`, `document`)
  - `components/layout/`: Shared layout frames
  - `components/modals/`: Global overlays
  - `components/shared/`: Reusable primitives

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

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.
