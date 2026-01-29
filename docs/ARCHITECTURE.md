# Architecture Overview

This document provides a high-level view of Tiger-Cafe's architecture, how the major subsystems interact, and where to look for core workflows.

## System Overview

Tiger-Cafe is a full-stack application that combines:

- **FastAPI backend** for authentication, document intake, processing, and data APIs
- **React frontend** for the shared global dashboard experience
- **Local storage + SQLite** for document artifacts and structured outputs
- **Gemini models** for classification, extraction, and summarization
- **Disk-based Cache** for full document text to speed up extraction

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
       └── Auth flow (Email/Password + JWT)
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
  - Searches for "GAAP reconciliation" or "EBITDA reconciliation" tables
  - Uses **Two-Step Filtering** (Number Density + Semantic Rank) to find the table
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
  - `auth.py`: JWT login flow, session management, and user seeding
  - `status_stream.py`: Real-time document status updates via SSE
  - `documents.py`: upload, indexing, and extraction triggers
  - `historical_calculations.py`: computes financial metrics
  - Additional routers: `balance_sheet.py`, `income_statement.py`, `organic_growth.py`, `amortization.py`, etc.
- **Services:** `app/services/`
  - `tiger_transformer_client.py`: Load and run inference on the local Tiger-Transformer model.
- **Models:** `app/models/` (SQLAlchemy)
- **Core:** `app/core/security.py` (JWT and Password utilities)
- **Schemas:** `app/schemas/` (Pydantic)
- **Utilities:** `app/utils/` (LLM and extraction helpers)

### Frontend (React + Vite)

- **Entry point:** `frontend/src/`
- **Pages:** `frontend/src/pages/`
  - `Dashboard.jsx`: **View Orchestrator** managing state (`GLOBAL`, `COMPANY`, `DOCUMENT`) and routing.
- **Global state & Logic:**
  - `frontend/src/contexts/`: `AuthContext` (User session), `ThemeContext` (UI theme).
  - `frontend/src/hooks/`: **Primary Business Logic** (`useDashboardData`, `useDocumentData`, `usePdfViewer`, `useUploadManager`).
- **Components:** `frontend/src/components/`
  - `views/`:
    - `global/`: `CompanyList`, `WelcomeView`
    - `company/`: `DocumentList`, `CompanyAnalysisView`, `FinancialModel`
    - `document/`: `PdfViewer`, `DocumentExtractionView`
  - `layout/`: Layout frames (`Header`, `SplitScreen`)
  - `modals/`: Global overlays (`UploadModal`, `UploadProgressModal`)
  - `shared/`: Reusable UI elements (`tables/`)

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
7. **Disk-Based Text Caching**: Full document text is extracted once and saved to disk (`data/storage/{doc_id}_full_text.txt`) to allow 10x faster access during subsequent extraction steps.
8. **Real-time Updates**: Document status is pushed to the frontend via Server-Sent Events (SSE) instead of polling.

### 2) The Multi-Stage Extraction Pipeline

Tiger-Cafe uses a robust, tiered approach to ensure high data integrity from financial documents.

#### 1. Stage 1: Finding & Completeness Audit
- **Section Search**: Uses Two-Step Filtering (Number Density + Semantic Rank) to find candidate chunks by reading from the disk-based cache.
- **Completeness Audit**: Gemini scans the chunk text to confirm it contains a *complete* financial statement (e.g., verifying it has both Cash and Total Liabilities). This prevents "hallucinating" values from partial overflow tables.

#### 2. Extraction & Refinement
- **Raw Extraction**: Gemini extracts line items exactly as they appear in the source text.
- **Ticker Reflection**: A specialized reflection step captures context around exchanges (NASDAQ/NYSE) to accurately identify tickers in microscopic sections.

#### 3. Classification & Standardization (Tiger-Transformer)
- **Unified Taxonomy**: Raw items are sent to the local **Tiger-Transformer** (FinnBERT) to map ad-hoc names to unified operating categories.
- **Mapping**: The model identifies `is_calculated`, `is_operating`, and `is_expense` flags for each item.

#### 4. Stage 2: Validation & Self-Correction
- **Mathematical Validation**: Checks if subtotals and totals match the sum of their components.
- **Reflection & Retry**: If a calculation imbalance is detected, the system sends the *exact error* back to Gemini for a "Precise Extraction" retry, effectively self-correcting previous mistakes.

#### 5. Additional Items Extraction
Dedicated agents run after main financial statements to identify "missing link" data:
- `Organic Growth`: M&A impact analysis
- `Amortization`: Operating vs Non-operating split
- `Shares Outstanding`: Basic/Diluted extraction
- `Other Assets/Liabilities`: Detailed breakdown for filings


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

### 4) Qualitative Assessment (Moat & Growth)

Before the DCF model is built, a dedicated qualitative analysis runs:
1.  **Agent**: `QualitativeAssessmentAgent` evaluates the company based on general LLM knowledge.
2.  **Output**: Determines:
    - **Economic Moat**: Width (Wide/Narrow/None) -> Impacts Terminal Growth Rate.
    - **Growth Trajectory**: (Faster/Steady/Slower) -> Impacts Stage 1 Growth Rate.
    - **Predictability**: (High/Medium/Low) -> Contextual confidence.
3.  **Integration**: These labels automatically adjust the default assumptions seeded into the Financial Model.

### 5) Financial Modeling (DCF Valuation)

1.  **Assumptions Management**:
    - Users input 3-stage growth assumptions (Revenue, Margins, Turnover) via UI.
    - Assumptions are stored in `financial_assumptions` table.
    - **Auto-Seeding**: Defaults are derived from Historical L4Q averages **AND** Qualitative Assessment overrides.
2.  **Projections Engine**:
    - Generates 10-year forecasts for P&L and Balance Sheet (Invested Capital).
    - Calculates Free Cash Flow (FCF) for each projected year.
3.  **Terminal Value**:
    - Uses Value Driver Formula: `NOPAT * (1 - g/RONIC) / (WACC - g)`.
    - Handles transition from explicit forecast period to steady state.
4.  **Valuation**:
    - Discounts FCF and Terminal Value using WACC (mid-year convention).
    - Sums PVs to derive Company Intrinsic Value.
    - Compares against Shares Outstanding for per-share value.

### 6) Analysis & Reporting

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

- **Automatic Seeding**: 
  In development mode (`ENVIRONMENT=development`), the application automatically seeds the database on startup (via `app/db/init_db.py`). This includes:
  - Default developer user (`dev@example.com`)
  - A comprehensive "Fake Railroad Company" demo dataset with historical financials and a processed DCF model for immediate testing and demonstration.

## Layered Architecture

### Layer Responsibilities

Tiger Cafe follows a strict layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    Routers Layer                             │
│  - HTTP endpoint definitions only                           │
│  - Request/response handling                                │
│  - Input validation (Pydantic)                              │
│  - Authentication checks                                    │
│  - NO business logic                                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Services Layer                             │
│  - Business logic and orchestration                         │
│  - Workflow coordination                                    │
│  - Transaction management                                   │
│  - Agent coordination                                       │
│  - NO HTTP concerns                                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agents Layer                              │
│  - LLM-powered extraction logic                             │
│  - Document section finding                                 │
│  - Financial statement parsing                              │
│  - Data transformation                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Models & Database                           │
│  - SQLAlchemy ORM models                                    │
│  - Database schema definitions                              │
│  - Relationships and constraints                            │
└─────────────────────────────────────────────────────────────┘
```

### 1. Routers Layer (`app/routers/`)

**Purpose**: HTTP endpoint definitions and request/response handling.

**Responsibilities**:
- Define API endpoints with FastAPI decorators
- Parse and validate request parameters (path, query, body)
- Handle authentication via dependency injection
- Delegate to service layer for business logic
- Format responses (HTTP status codes, JSON structure)
- Handle HTTP-specific errors (404, 400, etc.)

**Rules**:
- ✅ DO: Define endpoints, validate inputs, call services
- ❌ DON'T: Implement business logic, call agents directly, manage transactions

**Example**:
```python
@router.get("/{document_id}/balance-sheet")
async def get_balance_sheet(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get balance sheet for a document."""
    balance_sheet = db.query(BalanceSheet).filter(
        BalanceSheet.document_id == document_id
    ).first()
    
    if not balance_sheet:
        raise HTTPException(status_code=404, detail="Balance sheet not found")
    
    return {"status": "exists", "data": balance_sheet}
```

### 2. Services Layer (`app/services/`)

**Purpose**: Business logic orchestration and workflow coordination.

**Responsibilities**:
- Implement business workflows and processes
- Coordinate multiple agents and operations
- Manage database transactions
- Handle complex error scenarios
- Implement retry logic and fault tolerance
- Coordinate background tasks

**Rules**:
- ✅ DO: Orchestrate workflows, manage transactions, call agents
- ❌ DON'T: Handle HTTP requests, define endpoints, return HTTPException

**Example**:
```python
async def run_full_extraction_pipeline(document_id: str, db: Session):
    """Orchestrate the complete extraction pipeline."""
    document = db.query(Document).filter(Document.id == document_id).first()
    
    # 1. Extract Balance Sheet
    update_milestone(document_id, "balance_sheet", "in_progress")
    try:
        bs_data = extract_balance_sheet(
            document_id, 
            document.file_path, 
            document.time_period
        )
        save_balance_sheet(db, document_id, bs_data)
        update_milestone(document_id, "balance_sheet", "completed")
    except Exception as e:
        update_milestone(document_id, "balance_sheet", "error", str(e))
        raise
```

### 3. Agents Layer (`agents/`)

**Purpose**: LLM-powered extraction and transformation logic.

**Responsibilities**:
- Extract financial data from documents using LLMs
- Find relevant document sections via embeddings
- Parse and structure financial statements
- Transform raw data into standardized formats
- Validate extracted data

**Rules**:
- ✅ DO: Extract data, transform formats, validate outputs
- ❌ DON'T: Manage database sessions, handle HTTP, orchestrate workflows

**Example**:
```python
def extract_balance_sheet(
    document_id: str,
    file_path: str,
    time_period: str,
    max_retries: int = 4
) -> dict:
    """Extract balance sheet from document."""
    # Find the balance sheet section
    text, chunk_index = find_balance_sheet_section(document_id, file_path)
    
    # Extract line items using LLM
    extracted_data = extract_balance_sheet_llm(text, time_period)
    
    # Post-process and validate
    processed_items, errors = post_process_balance_sheet_line_items(
        extracted_data["line_items"]
    )
    
    return {
        "line_items": processed_items,
        "is_valid": len(errors) == 0,
        "validation_errors": errors,
        "chunk_index": chunk_index
    }
```

## Call Chain Flow

### Example: Document Upload and Extraction

```
1. Frontend uploads file
   └─> POST /api/documents/upload
       
2. Router (documents.py)
   ├─> Validates file
   ├─> Authenticates user
   └─> Calls upload_document_service()
       
3. Service (document_service.py)
   ├─> Saves file to disk
   ├─> Creates Document record in DB
   ├─> Triggers background ingestion
   └─> Returns document_id
       
4. Background Task (extraction_orchestrator.py)
   ├─> run_ingestion_pipeline()
   │   ├─> classify_document_agent()
   │   └─> index_document_agent()
   │
   └─> run_full_extraction_pipeline()
       ├─> extract_balance_sheet_agent()
       ├─> extract_income_statement_agent()
       ├─> extract_shares_outstanding_agent()
       └─> classify_non_operating_items_agent()
```

### Example: Fetching Extracted Data

```
1. Frontend requests data
   └─> GET /api/documents/{id}/balance-sheet
       
2. Router (extraction_tasks.py)
   ├─> Validates document_id
   ├─> Authenticates user
   └─> Queries database directly (simple read)
       
3. Database
   └─> Returns BalanceSheet with line_items
       
4. Router
   └─> Returns {"status": "exists", "data": {...}}
```

## Design Principles

### 1. Separation of Concerns

Each layer has a single, well-defined responsibility:
- **Routers**: HTTP protocol
- **Services**: Business logic
- **Agents**: Data extraction
- **Models**: Data structure

### 2. Dependency Flow

Dependencies flow in one direction:
```
Routers → Services → Agents → Models
```

Never reverse:
- ❌ Agents should NOT import from Services
- ❌ Services should NOT import from Routers
- ❌ Models should NOT import from Agents

### 3. No Circular Dependencies

If you need to share code:
- Extract to `app/utils/` for shared utilities
- Extract to `app/schemas/` for shared data structures
- Use dependency injection for database sessions

### 4. Transaction Management

- **Routers**: Never manage transactions
- **Services**: Own transaction boundaries
- **Agents**: Stateless, no database access

### 5. Error Handling

- **Routers**: Convert to HTTP errors (HTTPException)
- **Services**: Handle business errors, retry logic
- **Agents**: Raise descriptive exceptions

## Common Patterns

### Pattern 1: Simple CRUD Endpoint

```python
# Router
@router.get("/{id}")
async def get_item(id: str, db: Session = Depends(get_db)):
    item = db.query(Model).filter(Model.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item
```

### Pattern 2: Complex Workflow

```python
# Router
@router.post("/{id}/process")
async def trigger_processing(
    id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    background_tasks.add_task(process_service, id, db)
    return {"status": "started"}

# Service
async def process_service(id: str, db: Session):
    # Orchestrate multiple agents
    result1 = agent1.extract(id)
    result2 = agent2.transform(result1)
    
    # Save to database
    db.add(Result(data=result2))
    db.commit()
```

### Pattern 3: Agent Extraction

```python
# Agent
def extract_data(document_id: str, file_path: str) -> dict:
    # Find relevant section
    text = find_section(document_id, file_path)
    
    # Extract using LLM
    raw_data = llm_extract(text)
    
    # Validate and transform
    validated = validate_and_transform(raw_data)
    
    return validated
```

## Extension Points

- **New agents:** add under `agents/` and wire into queues in `app/utils/`.
- **New API endpoints:** add routers in `app/routers/` and schemas in `app/schemas/`.
- **New tables:** add SQLAlchemy models and regenerate baseline schema.
- **New services:** add to `app/services/` and call from routers.
- **New utilities:** add to `app/utils/` for shared functionality.
