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


## Section 3: UI/UX Implementation Plan

This section outlines the UI/UX changes required to support the new milestone structure and improved user feedback.

### 1. Centralized Progress Hub ("Check Updates" Page)
**Current File**: `frontend/src/components/modals/UploadProgressModal.jsx` (Partial implementation)
**Target File**: `frontend/src/components/views/global/CheckUpdatesView.jsx` (New)
**Backend Source**: `app/routers/status.py` (SSE Stream - New) / `app/routers/documents.py` (Current Polling)

**Goal**: Create a "Modern AI Agent" experience that transparently shows the system's "thought process" as it analyzes documents.

*   **Thought Process Stream**:
    *   Replace the generic progress bar with a granular, scrolling "Thought Stream" or "Log Stream".
    *   Display the **12 Milestones** defined in Section 2 as they occur.
    *   For each milestone, show its state: `pending` (dimmed), `in_progress` (pulse/spinner), `success` (green check), `warning` (yellow alert), `failure` (red X).
    *   Expandable details: Clicking a milestone reveals specific logs (e.g., "Scanning chunk 3...", "Validation failed, retrying...").
*   **Visual Phases**: Refine the high-level visual phases to map to the 12 granular steps:
    *   **Phase 1: Ingestion** (Steps 1-3: Upload, Classify, Index)
    *   **Phase 2: Core Extraction** (Steps 4-5: Balance Sheet, Income Statement)
    *   **Phase 3: Deep Analysis** (Steps 6-12: Additional Items, Non-Operating Classification)
*   **Technology**:
    *   Use **Server-Sent Events (SSE)** exclusively on this page to push real-time updates.
    *   Disable SSE on other pages to reduce server load.
*   **Cleanup**:
    *   Delete `frontend/src/components/modals/UploadProgressModal.jsx` after migrating logic.
    *   Remove usage of `UploadProgressModal` from `CompanyList.jsx`.
    *   Remove legacy polling endpoints (e.g., `get_upload_progress`) from `app/routers/documents.py`.

### 2. Document Extraction View Cleanup
**Goal**: Simplify the document view to focus on the result, not the process.

*   **Remove Progress Tracker**: Delete the legacy progress bar/stepper from the Document View.
*   **Validation Banner**:
    *   Add a static "Validation Status" banner at the top of the page.
    *   If `analysis_status` is `PROCESSED` but contains warning logs (e.g., missing GAAP tables), show a Yellow Warning Banner listing the missing items.
    *   If `analysis_status` is `ERROR`, show a Red Error Banner with the terminal error message.
    *   If `analysis_status` is `PROCESSED` (clean), show nothing.

### 3. Document List View Optimization
**Goal**: Only show ready-to-use documents to prevent user confusion.

*   **Filter Logic**:
    *   Modify the `DocumentList` component to filter out documents that are in active progress.
    *   **Logic**: Exclude if `indexing_status` is (`UPLOADING`, `CLASSIFYING`, `INDEXING`) OR `analysis_status` is (`PROCESSING`, `PENDING`).
    *   Only display documents with `analysis_status` of `PROCESSED` or `ERROR`.
*   **Remove "Processing" Badges**:
    *   Since unfinished documents are hidden, remove the "Processing..." chips/badges.


## Section 4: Testing Strategy

### Backend Tests (Pytest)
*   **New Tests**:
    *   `tests/routers/test_status.py`: Verify SSE endpoint connection and event streaming format.
    *   `tests/integration/test_pipeline_logging.py`: Ensure all 12 milestones (Upload -> Classification -> Extraction) emit correct start/success/failure logs.
    *   `tests/agents/test_gaap_warning.py`: Verify that missing GAAP reconciliation logs a Warning but does NOT raise an exception or fail the milestone.
*   **Updates**:
    *   `tests/routers/test_documents.py`: Update document status checks to respect the new `PROCESSED` vs `ERROR` logic.
*   **Removals**:
    *   Remove tests for `get_upload_progress` polling endpoint once deprecated.

### Frontend Tests (NPM / Playwright)
*   **New Tests**:
    *   `src/components/views/global/__tests__/CheckUpdatesView.test.jsx`: Test rendering of the 12-milestone stream and SSE event handling.
    *   `src/components/views/document/__tests__/DocumentValidation.test.jsx`: Verify Warning Banner appears when `analysis_status` is PROCESSED but warnings exist.
*   **Updates**:
    *   `tests/e2e/test_upload_flow.py`: Update End-to-End upload flow to check the "Check Updates" page instead of the Document List for progress.
    *   `src/components/views/company/__tests__/DocumentList.test.jsx`: Verify filter logic (Processing documents should be hidden).
*   **Removals**:
    *   Remove `src/components/modals/__tests__/UploadProgressModal.test.jsx`.
