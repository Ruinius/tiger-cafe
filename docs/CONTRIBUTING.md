# Contributing Guide

**Note: This is a personal project.**

I am sharing this code for educational purposes and to allow others to experiment with similar ideas. 

**I am not accepting Pull Requests or direct contributions to this repository at this time.**

However, you are welcome (and encouraged!) to:
- **Fork** this repository
- **Copy** the code
- **Experiment** and build upon it for your own projects

## For Your Reference: Development Workflow

If you are working on your own fork, here are the guidelines and tools I use:

### Getting Started

1. Follow the [Setup Guide](SETUP_GUIDE.md) to run the app locally.

### Code Style & Quality

I use pre-commit hooks for consistency:

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
