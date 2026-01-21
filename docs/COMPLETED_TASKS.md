# Completed Tasks

This document serves as an archive of completed tasks from the Project Planning.

## Phase 1: Foundation and Authentication
- [x] Project setup and structure
- [x] Git repository initialization
- [x] Basic configuration system (Gemini API setup)
- [x] Authentication system (Google OAuth)
- [x] Database schema design
- [x] Basic web framework setup (FastAPI)
- [x] Data structure definitions (SQLAlchemy models + Pydantic schemas)

## Phase 2: Document Upload and Classification
- [x] PDF upload functionality
- [x] PDF text extraction (first few pages and full document)
- [x] Document classification agent (LLM-based)
- [x] Duplicate detection system (content-based hash for all document types)
- [x] Document indexing with Gemini embeddings
- [x] Document metadata storage
- [x] Document summary generation (LLM-based, persisted in metadata)
- [x] User confirmation workflow
- [x] Priority-based processing queue for classification, indexing, and financial statements
- [x] Chunk-based document indexing

## Phase 3: Frontend UI - Login Page and Global Dashboard
- [x] Login Page: Google OAuth integration, error handling, loading states
- [x] Global Dashboard Layout: Vertical split screens, draggable divider, day/night toggle
- [x] Left Panel - Navigation: Company list, document button, company/document detail views
- [x] Right Panel - Content Display: Company analysis placeholder, document extraction view
- [x] Document Upload Flow Integration: Multi-doc upload, progress tracking, duplicate warnings

## Phase 4: Company and Document Management (Backend)
- [x] Company/Document listing API
- [x] Document status tracking (indexing, processing states)
- [x] Real-time status updates via polling
- [x] Document Type-Based Processing Status (CLASSIFIED for non-earnings docs)

## Phase 5: Financial Statement Processing
### 5.1 Balance Sheet Processing
- [x] Automatic sequential trigger (earnings announcements only)
- [x] Chunk embedding search for BS location
- [x] LLM-based extraction line-by-line
- [x] Two-stage validation: Section finding (Stage 1) and Calculation validation (Stage 2)
- [x] Line item classification
- [x] Data persistence and progress tracking
- [x] Re-run functionality

### 5.2 Income Statement Processing
- [x] Sequential trigger after BS
- [x] Location based on BS proximity
- [x] LLM-based extraction line-by-line
- [x] Additional data extraction (Shares, Amortization)
- [x] GAAP/EBITDA Reconciliation extraction (Earnings announcements)
- [x] Validation: Section finding (Stage 1) and Post-processing/diff logic (Stage 2)
- [x] Line item classification (Operating vs Non-operating)
- [x] Data persistence and progress tracking

### 5.3 Historical Calculations (Foundation)
- [x] Net Working Capital
- [x] Net Long Term Operating Assets
- [x] Invested Capital
- [x] Capital Turnover (Annualized)
- [x] EBITA & EBITA Margin
- [x] Effective Tax Rate
- [x] Display in Right Panel with re-run capability

### 5.4 Enhanced Historical Calculations
- [x] LLM-Enhanced Operating Income Identification
- [x] LLM-Enhanced Tax-Related Item Identification
- [x] Cost Format Normalization (Standardize to negative)
- [x] LLM-Enhanced Non-Operating Item Identification

### 5.5 & 5.6 Validation Enhancements
- [x] Completeness checks before extraction
- [x] Standard names for BS key items
- [x] Chunk index persistence

## Phase 6: Company Analysis and Adjustments
- [x] 6.1: Historical Calculations Table (Company View)
- [x] 6.2: Refactor for Additional Items (Backend models, routers, frontend scaffolding)
- [x] 6.3: Organic Growth Extraction (M&A impact logic)
- [x] 6.4: Amortization Extraction (Dedicated agent)
- [x] 6.5: Other Assets Extraction (Detailed breakdown)
- [x] 6.6: Other Liabilities Extraction (Detailed breakdown)
- [x] 6.7: Shares Outstanding Extraction (Dedicated agent)
- [x] 6.8: Non-Operating Asset Classification (Categorization of non-op items)
- [x] 6.9: Invested Capital Refinements (Excluding totals)
- [x] 6.10: Adjusted Tax Rate (Logic & Frontend)
- [x] 6.11: EBITA (Logic & Frontend adjustments)
- [x] 6.12: NOPAT and ROIC (Logic & Frontend)

## Phase 7: UI Standardization and Refinement
- [x] 7.1: Button Logic & UI Interaction Standardization
- [x] 7.2: Fine-Tuning UI Elements (Loading optimization, table headers, non-GAAP recon)
- [x] 7.3: Finalizing Historical Calculations & UI Polish (Ordering, grouping, formatting)
- [x] 7.4: Refactoring & Document Status UI (Pipeline order, authoritative lookups)
- [x] 7.5: Robust Extraction & Validation (Multi-stage checks)
- [x] 7.6: Adjusted Tax Rate, NOPAT, ROIC & UI Refinements (Consolidated done)

## Phase 8: Frontend Refactor & Code Organization
### 8.1 Stabilization (Phase 1)
- [x] Wrapped all Dashboard handlers in `useCallback`
- [x] Stabilized callback references to prevent unnecessary re-renders
- [x] Fixed `useEffect` dependencies in LeftPanel

### 8.2 Context Extraction (Phase 2)
- [x] Created `UploadContext` for global upload state management
- [x] Moved upload polling logic out of UI components
- [x] Wrapped app with `UploadProvider`
- [x] Updated LeftPanel to consume `useUpload()` hook
- [x] **Fixed infinite polling bug**

### 8.3 Component Split - Left Panel (Phase 3)
- [x] Extracted `PdfViewer` component
- [x] Extracted `CompanyList` component
- [x] Extracted `DocumentList` component
- [x] Extracted `UploadProgress` component
- [x] Refactored LeftPanel to compose smaller components

### 8.4 Component Split - Right Panel (Phase 4)
- [x] Extracted `CompanyAnalysisView` component
- [x] Extracted `DocumentExtractionView` component
- [x] Refactored RightPanel to use extracted components

### 8.5 Final Organization (Phase 5)
- [x] Created `WelcomeView` component for dashboard home
- [x] Moved `FinancialModel` to `analysis/` directory
- [x] Created `common/` directory for shared table components
- [x] Moved `LineItemTable`, `OrganicGrowthTable`, `StandardizedBreakdownTable`, `SharesOutstandingTable` to `common/`
- [x] Updated all import paths

## Phase 9: Financial Modeling (DCF Valuation)
- [x] 9.1: Historical Data Enhancements (Yields, Averages, medians, MCT)
- [x] 9.2: DCF Assumptions Framework (Organic Growth, Margins, WACC)
- [x] 9.3: DCF Calculations (FCF, Terminal Value, Intrinsic Value)
- [x] 9.4: UI Implementation (Input panel, 10-year projection table, Intrinsic Value bridge)
- [x] 9.5: Backend Enhancements (Calculations, persistence, valuation snapshots)

## Phase 10: View-Based Frontend Architecture Refactor
- [x] **Structural Reorganization**: Moved all components to `views/`, `layout/`, `modals/`, `shared/` structure.
- [x] **Monolith Elimination**: Deleted `LeftPanel.jsx` and `RightPanel.jsx`.
- [x] **Logic Extraction**: Created custom hooks (`useDashboardData`, `useDocumentData`, `usePdfViewer`, etc.) for business logic.
- [x] **Dashboard Orchestration**: Rewrite `Dashboard.jsx` to be the single source of truth for View State (`GLOBAL`, `COMPANY`, `DOCUMENT`).
- [x] **View Implementation**: Refactored `WelcomeView`, `CompanyList`, `DocumentList`, `CompanyAnalysisView`, `PdfViewer`, `DocumentExtractionView` to be standalone.
- [x] **UI Bug Fixes**: Restored document count badges, fixed PDF viewer height, and refined "Historical Calculations" table.

## Phase 11: User Authentication & Security
- [x] **JWT Implementation**: Stateless authentication using JWT App Tokens.
- [x] **Password Hashing**: Secure storage using BCrypt.
- [x] **Login Flow**: Refactored frontend to support Email/Password login.
- [x] **Auth Context**: Persistent sessions via LocalStorage.
- [x] **Developer Experience**: Automated user seeding (`dev@example.com`).

## Phase 12: Stream & Stability Improvements
- [x] **SSE Integration**: Replaced polling with Server-Sent Events for document status.
- [x] **Serialization Fixes**: Resolved JSON errors for Enums in long-running streams.
- [x] **E2E Reliability**: Created `scripts/seed_e2e_data.py` for consistent testing.
- [x] **Playwright Updates**: Updated E2E tests for new Auth and status patterns.
- [x] **React Reliability**: Fixed "unique key prop" warnings and field naming consistency.

## Phase 13: Tiger-Transformer Integration & Pipeline Refactor
(Implemented Phases 1-6 of the `docs/PIPELINE_REFACTOR.md` plan)

### 13.1 Database & Schema Preparation
- [x] Updated `app/models/balance_sheet.py` & `income_statement.py` (Added `standardized_name`, `is_calculated`, `is_expense`)
- [x] Updated Pydantic schemas in `app/schemas/`
- [x] Generated and applied Alembic migrations

### 13.2 Core Service Implementation
- [x] Created `app/services/tiger_transformer_client.py`
  - Model loading with local path check
  - Batch inference logic with context formatting
  - Caching for performance
- [x] Imported mapping files (`bs_calculated_operating_mapping.csv`, `is_calculated_operating_expense_mapping.csv`)

### 13.3 Balance Sheet Integration
- [x] **Extraction Prompt Update**: Enforced strict section tokens (`current_assets`, etc.)
- [x] **Transformer Integration**:
  - Rewrote `post_process_balance_sheet_line_items` to use `TigerTransformerClient`
  - Implemented "Section Tag Fallback" pre-processing
  - Automated `standardized_name`, `is_calculated`, `is_operating` population
- [x] **Validation Logic Update**:
  - Updated `validate_balance_sheet_calculations` to use standardized anchor names
  - Removed legacy `get_balance_sheet_llm_insights` & `classify_line_items_llm`

### 13.4 Income Statement Integration
- [x] **Extraction Prompt Update**: Enforced single `income_statement` token
- [x] **Transformer Integration**:
  - Rewrote `post_process_income_statement_line_items` to use `TigerTransformerClient`
  - Automated mapping population via `TigerTransformerClient`
- [x] **Normalization & Validation**:
  - Implemented expense sign enforcement (`is_expense=True` -> negative)
  - Implemented "Residual Solver" for `is_expense=None` sign ambiguity resolution
  - Removed legacy `get_income_statement_llm_insights` & `classify_line_items_llm`

### 13.5 Logging & Debugging Tools
- [x] Implemented exact input logging for transformer debugging (`balance_sheet_transformer_exact_inputs.csv`)
- [x] Created `scripts/export_retraining_data.py` (Planned)

### 13.6 Code Cleanup & Efficiency
- [x] Removed unused legacy agents and helper functions
- [x] Optimized pipeline by replacing multiple LLM calls with single transformer inference
- [x] Updated `ARCHITECTURE.md` and `DATABASE_SCHEMA.md` to reflect new flow

### Phase 13.7: Tiger-Transformer frontend fixes
- [x] Document Extraction View, Non-GAAP Reconcilidation - remove the "standardized name" column
- [x] Document Extraction View, Non-Operating Items Classification - several fixes
    - populate the standardized name column
    - replace the calculated column with the name of the classification (this field should already exist somewhere)
    - this table should only be filled with line items that are is_operating=false, is_calculated=false
    - in the bs_calculated_operating.csv, there should now be a column called nonoperating_category. Replace the LLM call for classification with just a lookup based on standardized name
- [x] Document Extraction View, Invested Capital Tables (there are three), replace category column with standardized name and ensure it is populated
- [x] Document Extraction View, Invested Capital Tables (there are three), double check the logic to show the items
    - the Net Working Capital table should be category=current_assets OR current_liabilities is_calculated=false, is_operating=true
    - the Net Long Term Operating Assets table should be category=noncurrent_assets OR noncurrent_liabilities is_calculated=false, is_operating=true
- [x] Document Extraction View, EBITA table and logic
    - there is a rare case where operating_income does not exist. In which case, the calculation should use income_before_taxes as the starting point
- [x] Document Extraction View, Adjusted Tax Rate table and logic
    - Effective Tax Rate should be calculated with income_tax_provision / income_before_taxes with fallbacks using standardized names
    - The Provision for Income Taxes line in the table and the logic is pulling incorrectly. Make sure it pulls from income_tax_provision
