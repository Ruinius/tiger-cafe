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
# Create frontend/.env with VITE_GOOGLE_CLIENT_ID

npm run dev
```

The frontend dev server defaults to http://localhost:3000.

## Configuration

Tiger-Cafe loads configuration from `.env` and `config/config.py`.

**Required environment variables:**

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Gemini API access for LLM + embeddings |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |

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
