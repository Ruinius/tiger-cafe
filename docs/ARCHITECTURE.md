# Architecture Overview

This document provides a high-level view of Tiger-Cafe's architecture, how the major subsystems interact, and where to look for core workflows.

## System Overview

Tiger-Cafe is a full-stack application that combines:

- **FastAPI backend** for authentication, document intake, processing, and data APIs
- **React frontend** for the shared global dashboard experience
- **Local storage + SQLite** for document artifacts and structured outputs
- **Gemini models** for classification, extraction, and summarization

```
┌────────────┐        ┌────────────────────┐        ┌──────────────┐
│  Frontend  │  HTTP  │     FastAPI API     │  ORM   │   SQLite DB  │
│  (React)   │  ───▶  │  (app/main.py)      │  ───▶  │ tiger_cafe.db│
└────────────┘        └────────────────────┘        └──────────────┘
       │                        │
       │                        ├── Document storage (data/uploads)
       │                        ├── Embeddings cache (data/cache)
       │                        └── Background queues (classification/indexing)
       │
       └── OAuth flow (Google)
```

## Key Components

### Backend (FastAPI)

- **Entry point:** `run.py` (runs `app.main:app`)
- **Routers:** `app/routers/`
  - `auth.py`: Google OAuth login flow
  - `documents.py`: upload, indexing, status, and extraction triggers
  - Additional routers house company/analysis APIs
- **Models:** `app/models/` (SQLAlchemy)
- **Schemas:** `app/schemas/` (Pydantic)
- **Utilities:** `app/utils/` (LLM and extraction helpers)

### Frontend (React + Vite)

- **Entry point:** `frontend/src/`
- **Pages:** `frontend/src/pages/`
- **Components:** `frontend/src/components/`
- **Global state:** `frontend/src/contexts/`

## Core Workflows

### 1) Document Upload & Classification

1. User uploads PDFs from the UI.
2. Backend stores files in `data/uploads`.
3. Classification job determines document type, company, and period.
4. Duplicate detection runs before indexing.
5. Embeddings are generated and persisted for reuse.

### 2) Financial Statement Extraction

1. Extract balance sheet + income statement from indexed content.
2. Validate line items and apply operating/non-operating classification.
3. Persist structured tables for downstream analysis.

### 3) Analysis & Reporting

1. Metrics are derived from extracted statements.
2. Analysis results are stored in `analysis_results`.
3. UI presents valuation models and summaries.

## Configuration & Data Paths

- `.env` holds API keys and overrides (see `config/config.py`).
- Default SQLite database: `tiger_cafe.db` in repo root.
- Data directories:
  - `data/uploads`: raw PDF uploads
  - `data/cache`: cached embeddings
  - `data/storage`: persisted artifacts
  - `logs/`: log output

## Extension Points

- **New agents:** add under `agents/` and wire into queues in `app/utils/`.
- **New API endpoints:** add routers in `app/routers/` and schemas in `app/schemas/`.
- **New tables:** add SQLAlchemy models and regenerate baseline schema.
