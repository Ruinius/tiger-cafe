# Contributing Guide

Thanks for contributing to Tiger-Cafe! This guide covers local setup, workflow expectations, and how to submit changes.

## Getting Started

1. Follow the [Setup Guide](SETUP_GUIDE.md) to run the app locally.
2. Create a feature branch from `main`:

```bash
git checkout -b <your-branch-name>
```

## Development Workflow

### Code Style & Quality

This repo uses pre-commit hooks for consistency:

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

Hooks include:
- `ruff` for linting + formatting
- `bandit` for security checks
- `detect-secrets` / `gitleaks` for credential scanning

### Python Formatting

- Use `ruff` for formatting.
- Avoid introducing `try/except` blocks around imports.

### Frontend Conventions

- Prefer functional React components.
- Keep UI state in contexts where appropriate.
- Use Axios for API calls (consistent with current code).

## Making Changes

1. Keep commits small and focused.
2. Update or add documentation alongside code changes.
3. If you add new models or fields, update:
   - `app/models/`
   - `docs/DATABASE_SCHEMA.md`
   - `migrate_baseline_schema.py` (when needed)

## Testing

Run the relevant checks before submitting:

```bash
# Backend checks (example)
python -m pytest

# Frontend checks (example)
npm run build
```

## Submitting a Pull Request

Include:

- A clear summary of the change
- Motivation and context
- Any testing performed

If you change UI behavior, include screenshots if possible.
