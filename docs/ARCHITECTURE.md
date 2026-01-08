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

## Document Type Processing Strategy

Tiger-Cafe processes different document types with varying levels of detail:

### Earnings Announcements
- **Full processing**: Classification, indexing, and financial statement extraction
- **Other Assets/Liabilities**: Extraction is completely skipped (no data is created)
  - The progress tracker does not report these as missing for earnings announcements
  - Frontend does not attempt to fetch other assets/liabilities endpoints for earnings announcements
- **GAAP/EBITDA Reconciliation**: Uses dedicated GAAP reconciliation extractor (exclusive to earnings announcements)
  - Searches for "GAAP reconciliation" or "EBITDA reconciliation" tables
  - Uses chunk-based embedding search with reranking (similar to balance sheet finding workflow)
  - Extracts amortization and other reconciliation line items from these tables
  - **Does not use** the amortization extractor

### Quarterly Filings (10-Q) & Annual Filings (10-K)
- **Full processing**: Classification, indexing, and financial statement extraction
- **Other Assets/Liabilities**: Full LLM-based extraction with detailed line item classification
- **Amortization**: Uses amortization extractor (general search approach)
  - Searches for amortization-related sections throughout the document
  - **Does not use** the GAAP reconciliation extractor

### Other Document Types
(Press releases, analyst reports, news articles, transcripts, etc.)
- **Classification only**: Document is classified and stored with `CLASSIFIED` status, but no indexing or financial statement extraction is performed
- Status: Documents receive `CLASSIFIED` status (not `CLASSIFYING` or `INDEXED`) to indicate classification completed but indexing skipped
- Users can view document metadata and summaries
- UI displays: "This document type is not yet implemented" message in the right panel

This approach optimizes processing costs and focuses detailed extraction on documents most likely to contain structured financial statements.

## Key Components

### Backend (FastAPI)

- **Entry point:** `run.py` (runs `app.main:app`)
- **Routers:** `app/routers/`
  - `auth.py`: Google OAuth login flow
  - `documents.py`: upload, indexing, status, and extraction triggers
  - `historical_calculations.py`: computes financial metrics
  - Additional routers: `balance_sheet.py`, `income_statement.py`, `organic_growth.py`, `amortization.py`, etc.
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
5. **Document type-based processing:**
   - **Earnings Announcements**: Full processing pipeline (indexing + financial statement extraction) → Status: `INDEXED`
   - **Quarterly Filings & Annual Filings**: Currently classification only → Status: `CLASSIFIED` (indexing and financial statement extraction not yet implemented)
   - **Other Document Types** (press releases, analyst reports, news articles, transcripts, etc.): Classification only → Status: `CLASSIFIED` (no indexing or financial statement extraction)
6. For eligible document types, embeddings are generated and persisted for reuse.

### 2) Financial Statement Extraction

**Eligible Document Types:**
- Earnings Announcements
- Quarterly Filings (10-Q)
- Annual Filings (10-K)

**Processing Differences by Document Type:**

1. **Earnings Announcements:**
   - Full balance sheet and income statement extraction
   - Other assets and other liabilities extraction is **completely skipped** (no data is created)
   - Progress tracker correctly handles this and does not report missing other assets/liabilities

2. **Quarterly Filings & Annual Filings:**
   - Full balance sheet and income statement extraction
   - Other assets and other liabilities use **LLM-based extraction** with detailed line item classification

**Extraction Process:**
1. Extract balance sheet + income statement from indexed content using chunk embeddings.
2. Two-stage validation:
   - Stage 1: Validate correct section found using full chunk text (retry with different chunks if needed)
   - Stage 2: Validate extraction accuracy with LLM feedback loop for error correction
   - Validation logic excludes "Total" category line items from sum calculations to avoid double counting
3. Apply operating/non-operating classification and persist structured tables for downstream analysis.
4. **Income Statement Line Item Categories:**
   - **Recurring**: Normal business operations that occur regularly
   - **One-Time**: Unusual or infrequent items
   - **Total**: Summary/total line items (e.g., "Total Net Revenue", "Total Expenses")
     - Totals do not have `is_operating` classification (set to `None`)
     - Exception: "Total Net Revenue" has `is_operating = True`
     - Totals are excluded from validation sum calculations to prevent double counting
5. **Additional Items Extraction**:
   - Dedicated agents run after main financial statements:
     - `Organic Growth`: M&A impact analysis
     - `Amortization`: Operating vs Non-operating split
     - `Shares Outstanding`: Basic/Diluted extraction
     - `Other Assets/Liabilities`: Detailed breakdown

### 3) Historical Calculation Subsystem

Triggered automatically after extraction milestones:
1.  **Data Ingestion**: Loads extracted Balance Sheet, Income Statement, and Additional Items.
2.  **Normalization**: Applies standard definitions (Standardized Names).
3.  **Computation**:
    - **Invested Capital**: Sum of NWC and Net Long-Term Assets.
    - **EBITA**: Operating Income - Non-Operating Items + Amortization.
    - **Tax**: Effective and Adjusted Tax Rates (using 25% marginal on adjustments).
    - **Performance**: NOPAT and ROIC (annualized).
4.  **Persistence**: Results saved to `historical_calculations` table.

### 4) Analysis & Reporting

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
