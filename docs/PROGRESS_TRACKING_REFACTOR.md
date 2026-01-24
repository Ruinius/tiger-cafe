# Progress Tracking UI/UX Refactor Plan

## Section 1: Current Milestones and Logs (Reference)

The system currently tracks the following milestones (`FinancialStatementMilestone`) and associated log messages. This section serves as a reference for existing logic.

### Milestones
1.  **`BALANCE_SHEET`** (`balance_sheet`)
2.  **`INCOME_STATEMENT`** (`income_statement`)
3.  **`EXTRACTING_ADDITIONAL_ITEMS`** (`extracting_additional_items`)
4.  **`CLASSIFYING_NON_OPERATING_ITEMS`** (`classifying_non_operating_items`)

### Log Messages Flow (Current)

#### 1. Balance Sheet
*   **Start**: `Started balance sheet extraction`
*   **Stage 1 (Section Finding)**:
    *   `Stage 1: Finding balance sheet section (attempt {N}, chunk {I})`
    *   `Checking chunk {I} (chars {start}-{end})`
    *   `Stage 1: Checking if chunk contains complete balance sheet using LLM`
    *   *Failure*: `Stage 1 validation failed: {reason}`
    *   *Success*: `Stage 1 validation passed (complete balance sheet chunk found and extracted)`
*   **Extraction**:
    *   `Extracting balance sheet from complete chunk`
    *   `Extracted {N} line items`
*   **Stage 2 (Validation)**:
    *   `Stage 2: Validating extraction calculations`
    *   `Classified {N} line items as operating/non-operating`
    *   *Time Period Check*: `Validation failed ({errors}). Checking for out-of-period line items.`
    *   *Removal*: `Removed {N} out-of-period items from {Total} total items. Re-validating.`
    *   *Retry*: `Validation still failed. Attempting final extraction with LLM feedback.`
    *   *Retry Success*: `Final retry extraction finished with {N} items. Re-validating.`
    *   *Success*: `Stage 2 validation passed` (optional: `(after LLM retry)` / `(deduced valid despite warnings)`)
    *   *Failure*: `Stage 2 validation failed after retries: {errors}`
*   **Completion**:
    *   `Balance sheet extraction completed`
    *   `Balance sheet processing completed` (Milestone Status: COMPLETED)
    *   OR `Balance sheet processed with validation errors` (Milestone Status: ERROR)

#### 2. Income Statement
*   **Start**: `Started income statement extraction`
*   **Stage 1 (Section Finding)**:
    *   `Stage 1: Finding income statement section (attempt {N}, chunk {I})`
    *   `Checking chunk {I} (chars {start}-{end})`
    *   `Stage 1: Checking if chunk contains complete income statement using LLM`
    *   *Failure*: `Stage 1 validation failed: {reason}`
    *   *Success*: `Stage 1 validation passed (complete income statement chunk found and extracted)`
*   **Extraction**:
    *   `Extracting income statement from complete chunk`
    *   `Extracted {N} line items`
*   **Stage 2 (Validation)**:
    *   `Stage 2: Post-processing and validating extraction`
    *   *Time Period Check*: `Validation failed ({errors}). Checking for out-of-period line items.`
    *   *Removal*: `Removed {N} out-of-period items...`
    *   *Retry*: `Validation still failed. Attempting final extraction with LLM feedback.`
    *   *Success*: `Stage 2 validation passed`
    *   *Failure*: `Stage 2 validation failed after retries: {errors}`
*   **Completion**:
    *   `Income statement extraction completed`
    *   `Classified {N} line items as operating/non-operating`
    *   `Income statement processing completed` (Milestone Status: COMPLETED)
    *   OR `Income statement processed with validation errors` (Milestone Status: ERROR)

#### 3. Additional Items (Milestone: `extracting_additional_items`)
*   **Start**: `Starting additional item extraction`
*   **Shares Outstanding**:
    *   `Extracting shares outstanding`
    *   *Success*: `Shares outstanding extracted`
    *   *Failure*: `Shares outstanding not found` OR `Shares outstanding extraction failed: {error}`
*   **GAAP Reconciliation** (Earnings Announcements):
    *   `Extracting GAAP/EBITDA reconciliation line items`
    *   *Chunk Checking*: `Checking chunk {I}... for complete GAAP to non-GAAP reconciliation table`
    *   *Completeness*: `Found complete reconciliation table...` OR `Chunk {I} does not contain complete table...`
    *   *Extraction*: `Extracting line items from operating income or EBITDA reconciliation table`
    *   *Count*: `Extracted {N} line items from reconciliation table`
    *   *Validation*: `Validation failed: {error}`, `Validation passed after removing out-of-period items`
    *   *Success*: `GAAP/EBITDA reconciliation extraction completed`
    *   *Failure*: `GAAP/EBITDA reconciliation extraction failed or not found`
*   **Amortization** (Others):
    *   `Extracting amortization line items`
    *   *Success*: `Amortization extraction completed`
    *   *Failure*: `Amortization extraction failed or not found`
*   **Organic Growth**:
    *   `Extracting organic growth signals`
    *   *Success*: `Organic growth extraction completed`
    *   *Failure*: `Organic growth extraction failed or insufficient data`
*   **Other Assets/Liabilities**:
    *   `Extracting other assets line items` / `Extracting other liabilities line items`
    *   *Success*: `Other assets extraction completed` / `Other liabilities extraction completed`
    *   *Failure*: `Other assets extraction failed or no line items found`
*   **Completion**:
    *   `Additional item extraction completed`
    *   OR `Additional item extraction completed with some errors: {errors}` (if any failed)

#### 4. Non-Operating Classification (Milestone: `classifying_non_operating_items`)
*   **Start**: `Classifying non-operating items...`
*   *Note: This usually runs implicitly at the end of the pipeline.*
*   **Completion**:
    *   `Classifying non-operating items completed`
    *   OR `Classification error: {error}`


## Section 2: NEW MILESTONES AND LOGS

This section details the proposed unified 12-step milestone structure, including detailed retries and error reasons.

### Proposed Milestones
1.  **`UPLOAD`** (`uploading`) - `app/routers/documents.py`
2.  **`CLASSIFICATION`** (`classifying`) - `app/services/document_processing.py`
3.  **`INDEX`** (`indexing`) - `app/services/document_processing.py`
4.  **`BALANCE_SHEET`** (`balance_sheet`) - `app/routers/balance_sheet.py`
5.  **`INCOME_STATEMENT`** (`income_statement`) - `app/routers/income_statement.py`
6.  **`SHARES_OUTSTANDING`** (`shares_outstanding`) - `app/routers/income_statement.py` (Agents: `agents/shares_outstanding_extractor.py`)
7.  **`ORGANIC_GROWTH`** (`organic_growth`) - `app/routers/income_statement.py` (Agents: `agents/organic_growth_extractor.py`)
8.  **`GAAP_RECONCILIATION`** (`gaap_reconciliation`) - `app/routers/income_statement.py` (Agents: `agents/gaap_reconciliation_extractor.py`)
9.  **`AMORTIZATION`** (`amortization`) - `app/routers/income_statement.py` (Agents: `agents/amortization_extractor.py`)
10. **`OTHER_ASSETS`** (`other_assets`) - `app/routers/income_statement.py` (Agents: `agents/other_assets_extractor.py`)
11. **`OTHER_LIABILITIES`** (`other_liabilities`) - `app/routers/income_statement.py` (Agents: `agents/other_liabilities_extractor.py`)
12. **`CLASSIFYING_NON_OPERATING_ITEMS`** (`classifying_non_operating_items`) - `app/routers/income_statement.py` (Agents: `agents/non_operating_classifier.py`)
13. **`UPDATE_HISTORICAL_DATA`** (`update_historical_data`) - `app/routers/companies.py`
14. **`UPDATE_ASSUMPTIONS`** (`update_assumptions`) - `app/routers/companies.py`
15. **`CALCULATE_INTRINSIC_VALUE`** (`calculate_intrinsic_value`) - `app/routers/companies.py`

### Statuses
*   `PENDING`
*   `IN_PROGRESS`
*   `COMPLETED`
*   `ERROR`
*   `WARNING` (New status for allowable missing data like optional tables)

### Detailed Flows

#### 1. Upload
*   **Start**: User initiates upload via API/UI.
*   **Success**: `File uploaded successfully` (Implicit in HTTP 200).
*   **Logs**: Currently no persistent logs.
*   **Status Transition**: `UPLOADING` -> `PENDING`.

#### 2. Classification
*   **Start**: `Classifying document type and company...` (Implicit from state).
*   **Success**: `Identified as {Type} for {Company} ({Ticker})`.
*   **Failure**: `Could not identify company (no ticker or name) from document`.
*   **Status Transition**: `CLASSIFYING` -> `CLASSIFIED` (or `INDEXING`).

#### 3. Index
*   **Start**: `Indexing document text and chunks...`
*   **Progress**: `Extracted {Pages} pages, {Chars} characters`.
*   **Success**: `Document indexed (Chunks: {N}, Embeddings generated).`
*   **Failure**: `Indexing failed: {Error}`.
*   **Status Transition**: `INDEXING` -> `INDEXED`.

#### 4. Balance Sheet
*   **Start**: `Started balance sheet extraction`
*   **Section Finding**:
    *   `Stage 1: Finding balance sheet section (attempt {N}, chunk {I})`
    *   `Checking chunk {I} (chars {start}-{end})`
    *   `Stage 1: Checking if chunk contains complete balance sheet using LLM`
    *   *Success*: `Stage 1 validation passed (complete balance sheet chunk found and extracted)`
    *   *Retry*: `Stage 1 validation failed: {reason}` (Will try next chunk)
*   **Extraction**:
    *   `Extracting balance sheet from complete chunk`
    *   `Extracted {N} line items`
*   **Validation & Retries**:
    *   `Stage 2: Validating extraction calculations`
    *   `Classified {N} line items as operating/non-operating`
    *   *Time Period Check*: `Validation failed ({errors}). Checking for out-of-period line items.`
    *   *Removal*: `Removed {N} out-of-period items from {Total} total items. Re-validating.`
    *   *LLM Retry*: `Validation still failed. Attempting final extraction with LLM feedback.`
    *   *Retry Success*: `Final retry extraction finished with {N} items. Re-validating.`
*   **Success**: `Balance sheet extraction completed`
*   **Failure**: `Stage 2 validation failed after retries: {errors}`

#### 5. Income Statement
*   **Start**: `Started income statement extraction`
*   **Section Finding**:
    *   `Stage 1: Finding income statement section...`
    *   `Checking chunk {I}...`
    *   `Stage 1: Checking if chunk contains complete income statement...`
*   **Extraction**:
    *   `Extracting income statement from complete chunk`
*   **Validation & Retries**:
    *   `Stage 2: Post-processing and validating extraction`
    *   *Time Period Check*: `Validation failed ({errors}). Checking for out-of-period line items.`
    *   *Removal*: `Removed {N} out-of-period items...`
    *   *LLM Retry*: `Validation still failed. Attempting final extraction with LLM feedback.`
*   **Success**: `Income statement extraction completed`
*   **Failure**: `Stage 2 validation failed after retries: {errors}`

#### 6. Shares Outstanding
*   **Start**: `Extracting shares outstanding`
*   **Success**: `Shares outstanding extracted`
*   **Failure**: `Shares outstanding extraction failed: {Error}` or `Shares outstanding not found`

#### 7. Organic Growth
*   **Start**: `Extracting organic growth signals`
*   **Success**: `Organic growth extraction completed`
*   **Warning**: `Organic growth section not found` (if harmless)
*   **Failure**: `Organic growth extraction failed: {Error}`

#### 8. GAAP Reconciliation (Earnings Only)
*   **Start**: `Extracting GAAP/EBITDA reconciliation`
*   **Progress**:
    *   `Checking chunk {I} (attempt {N}) for complete GAAP to non-GAAP reconciliation table`
    *   *Check*: `Checking if chunk {I} contains complete reconciliation table`
    *   *Found*: `Found complete reconciliation table in chunk {I}: {explanation}`
    *   *Not Found*: `Chunk {I} does not contain complete reconciliation table: {explanation}`
*   **Extraction**:
    *   `Extracting line items from operating income or EBITDA reconciliation table`
    *   `Extracted {N} line items from reconciliation table`
*   **Validation & Retries**:
    *   *Validation Error*: `Validation failed: {error}`
    *   *Time Period Check*: `Checking if line items belong to correct time period`
    *   *Removal*: `Removed {N} out-of-period items...`
    *   *Success After Removal*: `Validation passed after removing out-of-period items`
    *   *LLM Retry*: `Validation still failed... Attempting final extraction with validation feedback`
    *   *Final Retry Result*: `Final retry extracted {N} line items`
    *   *Final Success*: `Validation passed after final retry`
*   **Success**: `Non-GAAP reconciliation extraction completed: {N} line items`
*   **Warning**: `GAAP/EBITDA reconciliation extraction failed or not found (Warning)`
*   **Failure**: `Process failed: {Exception}` (if CRITICAL error)

#### 9. Amortization (Filings Only)
*   **Start**: `Extracting amortization line items`
*   **Retries**:
    *   *Duplicate Check*: `Duplicate amortization line item: {name}` (Warning inside logic)
    *   *LLM Retry*: (Implicit retry if validation fails or empty)
*   **Success**: `Amortization extraction completed`
*   **Warning**: `Amortization extraction failed or not found (Warning)`
*   **Failure**: `Amortization extraction failed: {Error}`

#### 10. Other Assets (Filings Only)
*   **Start**: `Extracting other assets line items`
*   **Success**: `Other assets extraction completed`
*   **Failure**: `Other assets extraction failed or no line items found`

#### 11. Other Liabilities (Filings Only)
*   **Start**: `Extracting other liabilities line items`
*   **Success**: `Other liabilities extraction completed`
*   **Failure**: `Other liabilities extraction failed or no line items found`

#### 12. Non-Operating Classification
*   **Start**: `Classifying non-operating items...`
*   **Success**: `Non-operating items classification completed`
*   **Failure**: `Classification error: {Error}`

#### 13. Update Historical Data
*   **Start**: `Updating historical data calculations...`
*   **Success**: `Historical data updated successfully`
*   **Failure**: `Failed to update historical data: {Error}`

#### 14. Update Assumptions
*   **Start**: `Updating financial assumptions...`
*   **Success**: `Financial assumptions updated`
*   **Failure**: `Failed to update assumptions: {Error}`

#### 15. Calculate Intrinsic Value
*   **Start**: `Calculating intrinsic value...`
*   **Success**: `Intrinsic value calculation completed`
*   **Failure**: `Failed to calculate intrinsic value: {Error}`



## Section 3: Router Refactor Plan

The current router structure suffers from poor separation of concerns:
- `income_statement.py` is monolithic, handling extraction for organic growth, shares, amortization, AND non-operating classification.
- `documents.py` handles upload but also has vestigial logic for processing progress.
- `additional_items.py` is read-only and defines schemas but contains no extraction logic.
- Pipeline triggering logic is scattered across `balance_sheet.py` and `documents.py`.

### Proposed Structure

#### 1. `app/routers/processing.py` (New)
**Orchestrates the extraction pipeline (HTTP layer only).**
- **Responsibility**: Receives HTTP requests and delegates to the service layer.
- **Endpoints**:
    - `POST /api/processing/documents/{document_id}/ingest`: Triggers Phase 1 (Classify → Index) *after* upload.
    - `POST /api/processing/documents/{document_id}/extract`: Triggers Phases 2-3 (Balance Sheet → Income Statement → Additional Items → Classification).
    - `POST /api/processing/documents/{document_id}/analyze`: Triggers Phase 4 (Analysis: Historical Data → Assumptions → Intrinsic Value). **User-triggered.**
    - `POST /api/processing/documents/{document_id}/rerun`: Re-runs the entire pipeline (clears existing data first).
    - `POST /api/processing/documents/{document_id}/retry/{milestone}`: Retries a specific failed milestone (e.g., `GAAP_RECONCILIATION`).
    - `GET /api/processing/documents/{document_id}/status`: Returns current granular progress (may be moved from `status_stream.py`).
- **Call Chain**: `processing.py` → `extraction_orchestrator.py` (service layer)
- **Why**: Centralizes pipeline control. Routers should only handle HTTP concerns (validation, auth, serialization).

#### 2. `app/routers/extraction_tasks.py` (Renamed from `additional_items.py`)
**Provides CRUD access to extracted auxiliary data.**
- **Responsibility**: REST API for reading/updating auxiliary financial data (Shares, Organic Growth, Amortization, Other Assets/Liabilities).
- **Current Endpoints** (Move from `additional_items.py`):
    - `GET /api/documents/{document_id}/amortization`
    - `GET /api/documents/{document_id}/organic-growth`
    - `GET /api/documents/{document_id}/other-assets`
    - `GET /api/documents/{document_id}/other-liabilities`
- **New Endpoints** (To be implemented):
    - `GET /api/documents/{document_id}/gaap-reconciliation`: Returns data extracted by `agents/gaap_reconciliation_extractor.py`.
    - `GET /api/documents/{document_id}/shares`: Returns data extracted by `agents/shares_outstanding_extractor.py`.
- **Does NOT contain extraction logic** (that lives in the service layer).
- **Why Rename**: "additional_items" is vague. "extraction_tasks" better reflects that this data comes from extraction tasks.

#### 3. `app/routers/income_statement.py` & `app/routers/balance_sheet.py` (Simplify)
**Handles CRUD for core financial statements.**
- **Responsibility**: Pure REST API for the resulting financial statement data.
- **Keep**:
    - `GET /api/documents/{document_id}/income-statement`: Retrieve income statement.
    - `GET /api/documents/{document_id}/balance-sheet`: Retrieve balance sheet.
- **Add** (for manual editing):
    - `PUT /api/documents/{document_id}/income-statement/line-items/{id}`: Update a line item.
    - `DELETE /api/documents/{document_id}/income-statement`: Clear the statement.
    - `PUT /api/documents/{document_id}/balance-sheet/line-items/{id}`: Update a line item.
    - `DELETE /api/documents/{document_id}/balance-sheet`: Clear the statement.
- **Remove**:
    - `process_income_statement_async` → Move to `extraction_orchestrator.py`
    - `process_balance_sheet_async` → Move to `extraction_orchestrator.py`
    - All background task logic → Move to service layer

#### 4. `app/routers/companies.py` (Minimal Changes)
**Handles company-level analysis (Phase 4).**
- **Keep existing endpoints** (they already work well):
    - `GET /api/companies/{company_id}/historical-calculations`
    - `GET /api/companies/{company_id}/assumptions`
    - `GET /api/companies/{company_id}/financial-model`
- **Add internal async functions** (for orchestrator to call):
    - `async def calculate_historical_data_task(company_id, db)`: Callable version of `get_company_historical_calculations`.
    - `async def update_assumptions_task(company_id, db)`: Callable version of `get_financial_assumptions`.
    - `async def calculate_intrinsic_value_task(company_id, db)`: Callable version of `get_financial_model`.

#### 5. `app/services/extraction_orchestrator.py` (New Service)
**Contains the actual extraction pipeline logic.**
- **Responsibility**: Coordinates the full extraction workflow (calls agents, saves to DB, updates progress).
- **Key Functions**:
    - `async def run_ingestion_pipeline(document_id, db)`: Runs Phase 1 (Classify → Index).
        - **Pre-requisite**: File is already uploaded and `Document` created by destruction `documents.py` router.
        - Calls `classify_document(extracted_text)`
        - Calls `index_document(document_id)`
        - Triggers `run_full_extraction_pipeline` upon success.
    - `async def run_full_extraction_pipeline(document_id, db)`: Runs Phases 2-3 sequentially.
        - Calls `extract_balance_sheet_task(document_id, db)`
        - Calls `extract_income_statement_task(document_id, db)`
        - Calls `extract_additional_items_task(document_id, db)` (which internally calls shares, organic growth, etc.)
        - Calls `classify_non_operating_items_task(document_id, db)`
        - Triggers `run_analysis_pipeline` upon completion (does not have to be success)
    - `async def run_analysis_pipeline(company_id, document_id, db)`: Runs Phase 4
        - **Document Level**: Calls `calculate_and_save_historical_calculations(document_id, db)` (from `historical_calculations.py`).
        - **Company Level**:
            - Calls `calculate_historical_data_task(company_id, db)` (Aggregation)
            - Calls `update_assumptions_task(company_id, db)`
            - Calls `calculate_intrinsic_value_task(company_id, db)`
    - `async def retry_milestone(document_id, milestone, db)`: Retries a specific failed step.
- **Why**: Separates business logic from HTTP handling. Easier to test, reuse, and maintain.

#### 6. `app/services/classification_service.py` (New Service)
**Handles non-operating classification logic.**
- **Responsibility**: Classifies balance sheet and income statement line items as operating/non-operating.
- **Key Functions**:
    - `async def classify_non_operating_items_task(document_id, db)`: Runs the classification agent and saves results.
- **Why**: Classification is a **post-processing step** that operates on already-extracted data. It's conceptually different from extraction and deserves its own service.

### Call Chain (Clarified)
```
User Request (HTTP: Upload File)
    ↓
app/routers/documents.py (Save File, Create Document Record)
    ↓
app/routers/processing.py (Trigger Ingestion)
    ↓
app/services/extraction_orchestrator.py (Business logic)
    ↓
Individual Task Functions:
    - run_ingestion_pipeline (Classify -> Index)
    - extract_balance_sheet_task
    - extract_income_statement_task
    - extract_additional_items_task (shares, organic growth, etc.)
    - classify_non_operating_items_task
    - calculate_and_save_historical_calculations (Phase 4a: Document Level)
    - calculate_historical_data_task (Phase 4b: Company Level Aggregation)
    - update_assumptions_task (Phase 4b)
    - calculate_intrinsic_value_task (Phase 4b)
    ↓
Agents (LLM calls)
    ↓
Database (Save results)
    ↓
Progress Tracking (Update milestones)
```

### Migration Steps
1.  **Refactor `documents.py` (Phase 1 Separation)**:
    - Modify `documents.py` to handle *only* file upload and initial `Document` creation.
    - Remove direct calls to `classification` and `indexing` logic from the upload route.
    - Ensure it returns the `document_id` so the frontend can immediately call `/ingest`.

2.  **Create Service Layer**:
    - Create `app/services/extraction_orchestrator.py`.
    - Implement `run_ingestion_pipeline`: Moves classification/indexing logic here.
    - Implement `run_full_extraction_pipeline`: Orchestrates Phase 2 & 3 tasks.
    - Implement `run_analysis_pipeline`: Orchestrates Phase 4 tasks.
    - Create `app/services/classification_service.py` and move non-operating logic there.

3.  **Create `processing.py` Router**:
    - Create `app/routers/processing.py`.
    - Add endpoints: `/ingest`, `/extract`, `/analyze` (Phase 4), `/rerun`, `/retry/{milestone}`, `/status` (SSE).
    - Wire endpoints to call the corresponding orchestrator functions.

4.  **Refactor Existing Routers**:
    - **`income_statement.py` & `balance_sheet.py`**: Strip out background tasks; keep CRUD.
    - **`additional_items.py`**: Rename to `extraction_tasks.py`. Add missing GET endpoints (`/shares`, `/gaap-reconciliation`).
    - **`companies.py`**: Expose internal async functions for Historical/Assumptions/Intrinsic Value for the orchestrator to call.

5.  **Update `app/main.py`**:
    - Add `processing.router` with prefix `/api/processing`.

6.  **Frontend Updates**:
    - **API Client**: Add methods for `/ingest`, `/extract`, `/analyze`, `retry`.
    - **Upload Flow**: Change to 2-step process: Upload File -> (Success) -> Call `/ingest`.
    - **Check Updates View**: Stream from `/api/processing/status` (SSE).
    - **Document View**: Rewire "Re-run Extraction" button to call `/api/processing/documents/{id}/rerun`

7.  **Cleanup**:
7.  **Cleanup**:
    - **Remove Legacy Functions**:
        - `app/routers/balance_sheet.py`: `process_balance_sheet_async`
        - `app/routers/income_statement.py`: `process_income_statement_async`
        - `app/routers/documents.py`: Legacy progress checking logic (e.g., `_active_progress_milestone`).
    - **Remove/Update Tests**:
        - `tests/test_earnings_announcement_extractors.py`: Update to call orchestrator instead of direct router functions.
        - `tests/test_filing_extractors.py`: Update similarly.
    - **Documentation**:
        - Update ARCHITECTURE.md