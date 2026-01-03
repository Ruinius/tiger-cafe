# Setup Guide

This guide walks through getting Tiger-Cafe running locally (backend + frontend) with the expected directory structure and configuration.

## Prerequisites

- Python 3.8+
- Node.js (18+ recommended) + npm
- Git
- Google Cloud project for OAuth credentials
- Google AI Studio account for a Gemini API key

## Clone the Repository

```bash
git clone <repository-url>
cd tiger-cafe
```

## Backend Setup

### 1) Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 2) Install Dependencies

```bash
pip install -r requirements.txt
```

**Optional (recommended):** use `uv` for consistent dependency installs.

```bash
pip install uv
uv pip install -r requirements.txt
```

### 3) Configure Environment Variables

Create a `.env` file in the project root (you can copy `keys.example.txt`):

```bash
cp keys.example.txt .env
```

Update the values in `.env`:

```
GEMINI_API_KEY=your-gemini-api-key-here
GOOGLE_CLIENT_ID=your-google-client-id-here
GOOGLE_CLIENT_SECRET=your-google-client-secret-here
```

Optional settings (defaults are defined in `config/config.py`):

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./tiger_cafe.db` | Database connection string |
| `ENVIRONMENT` | `development` | Environment name |
| `DEBUG` | `true` in development | Enables dev-only endpoints |

### 4) Create Required Directories

```bash
mkdir -p data/cache data/storage data/uploads logs
```

### 5) Initialize the Database

The database schema is created automatically on app start. To reset or bootstrap explicitly:

```bash
python migrate_baseline_schema.py
```

### 6) Start the Backend Server

```bash
python run.py
```

API endpoints:
- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Frontend Setup

```bash
cd frontend
npm install
```

Create `frontend/.env` with:

```
VITE_GOOGLE_CLIENT_ID=your-google-client-id-here
```

Start the dev server:

```bash
npm run dev
```

The frontend is available at http://localhost:3000 by default.

## Pre-commit Hooks (Recommended)

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

Installed hooks:
- `detect-secrets`, `gitleaks`, `detect-private-key`
- `bandit` for Python security scanning
- `ruff` for linting + formatting

## Troubleshooting

### Authentication Errors

- Confirm `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`.
- Ensure redirect URIs include `http://localhost:8000/api/auth/callback`.

### Database Reset

```bash
rm tiger_cafe.db  # Windows: del tiger_cafe.db
python migrate_baseline_schema.py
```

### Import Errors

- Ensure the virtual environment is active.
- Reinstall dependencies: `pip install -r requirements.txt`.

### Pre-commit Failures

```bash
uv run pre-commit autoupdate
uv run pre-commit run --all-files --verbose
```

If you must bypass hooks for a single commit (not recommended):

```bash
git commit --no-verify
```
