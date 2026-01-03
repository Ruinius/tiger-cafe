# Setup Guide

This guide will help you set up the Tiger-Cafe application for development.

## Prerequisites

- Python 3.8 or higher
- Git (for version control)
- Google Cloud Platform account (for OAuth credentials)
- Google AI Studio account (for Gemini API key)

## Initial Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd tiger-cafe
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note:** This project uses `uv` for improved dependency management and environment handling. If you want to use `uv` (recommended):
```bash
# Install uv
pip install uv
# Or use standalone installer: https://github.com/astral-sh/uv

# Install dependencies with uv
uv pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root (you can copy from `keys.example.txt`):

```bash
GEMINI_API_KEY=your-gemini-api-key-here
GOOGLE_CLIENT_ID=your-google-client-id-here
GOOGLE_CLIENT_SECRET=your-google-client-secret-here
```

#### Getting API Keys:

1. **Gemini API Key**:
   - Go to https://makersuite.google.com/app/apikey
   - Create a new API key
   - Copy it to your `.env` file

2. **Google OAuth Credentials**:
   - Go to https://console.cloud.google.com/apis/credentials
   - Create a new OAuth 2.0 Client ID
   - Set authorized redirect URIs (e.g., `http://localhost:8000/api/auth/callback`)
   - Copy the Client ID and Client Secret to your `.env` file

### 5. Create Required Directories

```bash
mkdir -p data/cache
mkdir -p data/storage
mkdir -p data/uploads
mkdir -p logs
```

### 6. Initialize Database

**Automatic Schema Creation:**
The database schema is automatically created from SQLAlchemy models when you start the application. The SQLite database file will be created at `tiger_cafe.db` in the project root.

**Manual Database Setup (optional):**
For a fresh database or to reset an existing one, you can run the baseline migration:
```bash
python migrate_baseline_schema.py
```

This creates all tables from the current model definitions. See [MIGRATION_GUIDE.md](../MIGRATION_GUIDE.md) for more details.

### 7. Set Up Pre-commit Hooks (Recommended)

Pre-commit hooks ensure code quality, security, and consistency:

```bash
# Install pre-commit hooks
uv run pre-commit install

# Or if uv is not available:
pre-commit install
```

**What it does:**
- Automatically runs code quality checks on `git commit`
- Checks for secrets, security issues, and code style
- Formats code with ruff
- Blocks commits with issues

**Manual run:**
```bash
# Run all hooks on all files
uv run pre-commit run --all-files

# Or without uv:
pre-commit run --all-files
```

**Hooks installed:**
- `detect-secrets` - Scans for API keys and secrets
- `gitleaks` - Additional secret detection
- `detect-private-key` - Catches private key files
- `bandit` - Python security linter
- `ruff` - Python linter and formatter (replaces black, isort, flake8)
- `check-added-large-files` - Prevents large file commits
- `check-merge-conflict` - Catches merge conflicts

## Running the Application

### Development Server

```bash
python run.py
```

Or using uvicorn directly:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Alternative API Documentation: http://localhost:8000/redoc

## Project Structure

See [README.md](../README.md) for the complete project structure.

## Database Schema

See [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for detailed database schema documentation.

## Next Steps

1. Set up your frontend (when ready)
2. Implement document upload functionality (Phase 2)
3. Build document classification agents
4. Implement financial analysis agents

## Troubleshooting

### Database Issues

If you need to reset the database:

```bash
# Delete the database file
rm tiger_cafe.db  # On Windows: del tiger_cafe.db

# Option 1: Restart the application (database will be recreated automatically)
python run.py

# Option 2: Run the baseline migration explicitly
python migrate_baseline_schema.py
```

### Authentication Issues

- Ensure your Google OAuth credentials are correctly set in `.env`
- Check that authorized redirect URIs match your application URLs
- Verify that the GOOGLE_CLIENT_ID matches your OAuth client configuration

### Import Errors

If you encounter import errors, make sure:
- Your virtual environment is activated
- All dependencies are installed: `pip install -r requirements.txt`
- You're running commands from the project root directory

### Pre-commit Hook Issues

If pre-commit hooks are failing:

```bash
# Update hooks to latest versions
uv run pre-commit autoupdate

# Run hooks with verbose output to see errors
uv run pre-commit run --all-files --verbose

# Skip hooks for a single commit (not recommended)
git commit --no-verify
```

**Common Issues:**
- **Bandit encoding errors**: Resolved by using `uv run pre-commit` which handles encoding correctly
- **Ruff auto-fixes**: Ruff may modify files. Review changes and commit them.
- **Secret detection false positives**: Review `.secrets.baseline` file and update if needed

