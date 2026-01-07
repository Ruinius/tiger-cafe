# Tiger-Cafe Project Planning

**A private project for Tiger and his friends to play with AI agents performing financial analysis.**

## Project Goals

Build AI agents that can analyze equity investments using principles from Tim Koller's Valuation methodology. The system will provide rigorous financial analysis, intrinsic value calculations, and market sensitivity assessments. This is a personal project for experimentation and learning.

## Key Features (Planned)

1. **Financial Data Parsing and Extraction**
   - Extract and parse financial statements
   - Process company financials and fundamentals
   - Data normalization and structuring

2. **Financial Statement Adjustments**
   - Adjust financial statements based on Tim Koller's Valuation principles
   - Normalize accounting treatments for accurate comparison
   - Handle non-operating items and adjustments

3. **Financial Metrics Assessment**
   - Organic growth analysis
   - Operating margin assessment
   - Capital turnover evaluation

4. **Intrinsic Value Calculations**
   - Calculate intrinsic value based on Tim Koller's Valuation methodology
   - DCF (Discounted Cash Flow) modeling
   - Valuation framework implementation

5. **Market Analysis**
   - Market belief analysis
   - Sensitivity analysis for key assumptions
   - Scenario modeling

6. **Agent Architecture**
   - Modular agent design
   - Specialized agents for different analysis stages
   - Agent coordination and workflow

## User Journey Epics

### Epic 1: Document Upload and Classification (Complete)

**User Flow:**
1. User logs in using Google account (OAuth)
2. User clicks "Add Document" button
3. User drags and drops or selects multiple PDF documents (up to 10 files)
4. Modal closes immediately after file selection
5. System processes documents asynchronously in background:
   - Uploads files to server
   - Reads first few pages for initial classification, then full document for final processing
   - LLM determines:
     - Document type (earnings announcement, quarterly filing, annual filing, other press release, analyst report, news article)
     - Time period
     - Company identification
     - Generates preliminary summary
   - Checks for duplicates (content-based hash for all types)
   - If duplicate detected: stops at Classification milestone, shows warning with "Replace & Index" button
   - If no duplicate: automatically proceeds to indexing
6. **Document type-based processing:**
   - **Earnings Announcements**: Proceed to indexing → Status: `INDEXED`
   - **Quarterly Filings, Annual Filings**: Classification only → Status: `CLASSIFIED` (indexing not yet implemented)
   - **Other Document Types** (press releases, analyst reports, news articles, transcripts, etc.): Classification only → Status: `CLASSIFIED` (no indexing or financial statement extraction)
7. For eligible document types, index document using Google's embedding model (gemini-embedding-001)
   - Documents are split into 2-page chunks for indexing
   - Chunk embeddings are generated and persisted to disk
   - Classification and indexing happen sequentially via priority queue (high priority)
   - Upload step is parallel, but classification/indexing are sequential
8. After indexing completes, automatically trigger financial statement processing (for eligible document types):
   - Financial statement processing is queued with lower priority
   - Classification/indexing tasks are always processed before financial statement extraction
   - Balance sheet extraction and classification (runs first)
   - Income statement extraction, additional items extraction, and classification (runs after balance sheet completes)
   - **Earnings Announcements**: 
     - Other assets/liabilities extraction is completely skipped (no data is created)
     - GAAP/EBITDA reconciliation extraction uses dedicated extractor (exclusive to earnings announcements)
     - **Does not use** the amortization extractor
   - **Quarterly/Annual Filings**: 
     - Other assets/liabilities use full LLM-based extraction
     - Amortization extraction uses general amortization search approach
     - **Does not use** the GAAP reconciliation extractor
   - Processing runs sequentially via global queue to avoid overwhelming Gemini API
8. User can view progress by clicking "Check Uploads" button (shows upload progress view with milestones)
9. System automatically navigates back to companies list when uploads complete
10. User can view financial statement processing progress in real-time in the right panel when viewing a document
    - Progress tracker shows 5 milestones with status: checking, pending, in_progress, completed, error, not_found
    - Financial statements load only when all milestones are terminal

### Epic 2: Company Document Management and Analysis Triggering

**User Flow:**
1. User logs in using Google account
2. User views list of companies with uploaded documents
3. User selects a company
4. System displays:
   - List of documents with:
     - Short summary (persisted from initial upload)
     - Number of pages
     - Number of characters
     - Time uploaded
     - Indexing status (with progress tracking bar)
     - Financial statement processing status
5. Financial statement processing (balance sheet and income statement) is automatically triggered sequentially after document indexing completes (for earnings announcements only - quarterly/annual filings not yet implemented)
   - Earnings announcements completely skip other assets/liabilities extraction (no data is created)
   - Quarterly/annual filings use LLM-based extraction for other assets/liabilities
6. User can view real-time progress in right panel with 5 milestones tracked (extracting balance sheet, classifying balance sheet, extracting income statement, extracting additional items, classifying income statement)
7. User can re-run processing using "Re-run Extraction and Classification" button in document detail view (re-runs entire pipeline)
8. User can delete financial statements or entire document using delete buttons in document detail view

### Epic 3: Financial Metrics Display and Analysis

**User Flow:**
1. User logs in and views list of companies with pending/completed analysis
2. User selects a company that recently completed analysis
3. System displays:
   - List of persisted financial metrics for trend analysis
   - Valuation model with adjustable assumptions
   - Sensitivity analysis with adjustable assumptions
   - LLM-driven summaries of:
     - Analyst reports (from uploaded documents)
     - Online searches on future organic growth, operating margin, and capital turnover (future feature)

## Technology Stack

- **Language**: Python
- **AI/ML**: 
  - Google Gemini (gemini-2.5-flash-lite) with very low temperature (0.1) for consistent analysis
  - Google Gemini Embedding (gemini-embedding-001) for document indexing
  - Using `google.genai` API (migrated from deprecated `google.generativeai`)
  - Centralized API client with throttling, retry logic, and processing queues
  - Chunk-based indexing (2-page chunks) with persisted embeddings
  - Priority-based processing queue (classification/indexing prioritized over financial statements)
- **Web Framework**: FastAPI (with Uvicorn)
- **Frontend**: React with Vite
  - React Router for navigation
  - Context API for global state (Auth, Theme)
  - Axios for API calls
- **Authentication**: Google OAuth (using google-auth and google-oauth2-id-token)
- **Document Processing**: PDF parsing libraries (PyPDF2, pdfplumber, etc.)
- **Data Processing**: Pandas, NumPy, yfinance
- **Database**: SQLite (SQLAlchemy ORM) - can be upgraded to PostgreSQL later
- **Storage**: Local cache + database for persistence
- **Configuration**: python-dotenv for API key management

## Development Phases

### Phase 1: Foundation and Authentication (Complete)
- [x] Project setup and structure
- [x] Git repository initialization
- [x] Basic configuration system (Gemini API setup)
- [x] Authentication system (Google OAuth)
- [x] Database schema design
- [x] Basic web framework setup (FastAPI)
- [x] Data structure definitions (SQLAlchemy models + Pydantic schemas)

### Phase 2: Document Upload and Classification (Complete)
- [x] PDF upload functionality
- [x] PDF text extraction (first few pages and full document)
- [x] Document classification agent (LLM-based)
  - Document type detection
  - Time period extraction
  - Company identification
- [x] Duplicate detection system (content-based hash for all document types)
- [x] Document indexing with Gemini embeddings
- [x] Document metadata storage
- [x] Document summary generation (LLM-based, persisted in metadata)
- [x] User confirmation workflow
- [x] Priority-based processing queue for classification, indexing, and financial statements
  - Upload step happens in parallel (file I/O only)
  - Classification and indexing happen sequentially via priority queue (high priority)
  - Financial statement processing happens sequentially via priority queue (lower priority)
  - High-priority tasks (classification/indexing) are always processed before lower-priority tasks (financial statements)
  - Prevents overwhelming Gemini API during batch uploads
- [x] Chunk-based document indexing
  - Documents split into 2-page chunks for embedding generation
  - Chunk embeddings are persisted to disk and reused
  - Eliminates duplicate embedding generation during extraction
  - More efficient than document-level embeddings

### Phase 3: Frontend UI - Login Page and Global Dashboard
Based on UI/UX Design specifications, build the frontend interface:

#### 3.1: Login Page
- [x] Frontend framework setup (React with Vite)
- [x] Login page UI with centered Google OAuth button
- [x] Google OAuth integration on frontend
- [x] Error handling UI (OAuth cancellation, network errors, etc.)
- [x] Loading states during authentication
- [x] Post-login redirect to dashboard

#### 3.2: Global Dashboard Layout
- [x] Two adjustable split screens (vertical split)
- [x] Draggable divider for resizing (20% to 80% range, default 50%)
- [x] Split preference persistence (per user, stored in localStorage)
- [x] Day/Night toggle functionality
  - Toggle button in header
  - Color scheme implementation (day/night modes)
  - Preference persistence
  - Smooth transitions

#### 3.3: Left Panel - Navigation (Complete)
- [x] Company list view
  - List of all companies (shared dashboard)
  - Company name and ticker display
  - Search/filter functionality
  - Click to navigate to company detail
- [x] Add document button (bottom of left panel, available in all views)
- [x] Company detail view (when company selected)
  - Document list for selected company
  - Document cards showing type and time period (instead of filename)
  - Status indicators with full timestamp
  - Click to navigate to document detail
- [x] Document detail view (when document selected)
  - Document information display (status, metadata, summary)
  - PDF viewer in left panel
  - Navigation back to company
- [x] Document count badges (on company list items)
- [x] Breadcrumb navigation
- [x] Attribution display (uploader name, timestamp)

#### 3.4: Right Panel - Content Display
- [x] Default home page
  - Placeholder for latest completed company analyses
- [x] Company analysis page (when company selected)
  - Placeholder for company analysis results
- [x] Document extraction view (when document selected)
  - Extracted information display (summary, classification results)
  - Classification results (type, time period, pages, characters)

#### 3.5: Document Upload Flow Integration (Complete)
- [x] Multi-document upload modal (drag-and-drop, up to 10 files)
- [x] Modal closes immediately after file selection
- [x] Add Document button transforms to "Check Uploads" with spinner during active uploads
- [x] Upload progress view in left panel (replaces company list)
- [x] Progress bar with three milestones: Uploading → Classification → Indexing
- [x] Real-time progress updates via polling (every 2 seconds)
- [x] Duplicate detection stops progress before indexing
- [x] Duplicate warning with "Replace & Index" button in progress view
- [x] Automatic progression when no duplicates detected
- [x] Background async processing for all steps
- [x] Automatic navigation back to companies list when uploads complete
- [x] Batch upload endpoint supporting up to 10 files
- [x] Upload progress tracking endpoint
- [x] Replace & Index endpoint for handling duplicate replacements

### Phase 4: Company and Document Management (Epic 2 - Backend Integration)
- [x] Company listing API integration
- [x] Company document listing API integration
- [x] Document status tracking (indexing, processing)
  - Statuses: PENDING, UPLOADING, CLASSIFYING, CLASSIFIED, INDEXING, INDEXED, ERROR
    - CLASSIFIED: Terminal state for documents that have been classified but indexing was skipped (non-earnings announcements, quarterly/annual filings not yet implemented)
  - Duplicate detection flags (duplicate_detected, existing_document_id)
- [x] Real-time status updates (polling mechanism)
- [x] Progress indicators for indexing/processing (in upload progress view and document list)
- [x] Document summary persistence and display
  - Summary generated during initial upload (LLM-based)
  - Displayed in document detail view and upload workflow
- [x] **Document Type-Based Processing Status:**
  - Add `CLASSIFIED` status for non-earnings announcements (terminal state after classification)
  - Update UI to display "This document type is not yet implemented" message for non-eligible document types
  - Add comprehensive tests for `CLASSIFIED` status functionality
  - Update documentation to reflect new status and user experience

### Phase 5: Financial Statement Processing

#### 5.1: Balance Sheet Processing (Complete)
- [x] Automatic trigger: Balance sheet processing automatically starts after document indexing completes (for earnings announcements only - quarterly/annual filings not yet implemented)
- [x] Sequential processing: Balance sheet and income statement processing run sequentially (not in parallel) to avoid overwhelming Gemini API
- [x] Use persisted chunk embeddings to locate the consolidated balance sheet section
  - Reuses chunk embeddings generated during document indexing
  - No duplicate embedding generation during extraction
  - Efficient chunk-level embedding search for precise location
  - Document type-based search range restrictions:
    - Earnings announcement: ignore first 30% and last 10% of document
    - Annual filing: ignore first 50% and last 20% of document
    - Quarterly filing: ignore last 50% of document (no front ignore)
  - Two-stage validation with retry strategy (see sections 5.5 and 5.6 for details):
    - Stage 1: Try rank 1, 2, 3 chunks to find correct section (LLM completeness check on chunk text before extraction)
    - Stage 2: Retry extraction up to 3 times with LLM feedback if sum validation fails
- [x] LLM-based extraction of balance sheet line items:
  - Extract balance sheet exactly line by line for the specified time period
  - Extract local currency when applicable
  - Extract unit of measurement (ones, thousands, millions, billions, or ten_thousands for foreign stocks)
- [x] Validation and error handling (see sections 5.5 and 5.6 for two-stage validation details):
  - Stage 1 validation: LLM completeness check on chunk text (validates chunk contains complete balance sheet before extraction)
  - Stage 2 validation: Verify that current assets sum correctly, total assets sum correctly, current liabilities sum correctly, total liabilities sum correctly, and total assets equal total liabilities and total equity
  - Precise total identification using regex to handle long line item names with notes
  - LLM feedback loop: If sum validation fails, retry extraction with validation errors and calculated differences included in prompt
  - Validation runs in frontend (not persisted) to avoid blocking on validation errors
- [x] Line item classification:
  - Use authoritative lookup table with normalization for binding decisions
  - Fallback heuristics when no lookup match
  - LLM classification for remaining items
  - Normalization: trim, case-insensitive, collapse whitespace, remove punctuation
- [x] Data persistence and display:
  - Persist balance sheet extraction and line item classification
  - Display balance sheet data in right panel when document is selected in left panel
- [x] Real-time progress tracking:
  - Async progress tracking with polling
  - Milestone tracking: extracting balance sheet, classifying balance sheet
  - Status display in right panel with real-time updates
- [x] Re-run functionality:
  - Single "Re-run Extraction and Classification" button that re-runs entire pipeline
  - Button immediately sets all milestones to pending and starts polling

#### 5.2: Income Statement Processing (Complete)
- [x] Automatic trigger: Income statement processing automatically starts after balance sheet processing completes (for earnings announcements only - quarterly/annual filings not yet implemented)
- [x] Sequential processing: Runs after balance sheet processing to avoid overwhelming Gemini API
- [x] Use balance sheet location to locate income statement:
  - First finds balance sheet location using chunk embeddings
  - Two-stage validation with retry strategy (see sections 5.5 and 5.6 for details):
    - Stage 1: Try chunks before, after, and 2 after balance sheet to find correct section (LLM completeness check on chunk text before extraction)
    - Stage 2: Retry extraction up to 3 times with LLM feedback if post-processing validation fails
  - More reliable than independent search since income statements are typically near balance sheets
  - Document type-based search range restrictions (same as balance sheet):
    - Earnings announcement: ignore first 30% and last 10% of document
    - Annual filing: ignore first 50% and last 20% of document
    - Quarterly filing: ignore last 50% of document (no front ignore)
- [x] LLM-based extraction of income statement line items:
  - Extract income statement exactly line by line for the specified time period
  - Extract local currency when applicable
  - Extract unit of measurement (ones, thousands, millions, billions, or ten_thousands for foreign stocks)
  - Extract revenue for the same period in the prior year (for year-over-year growth calculation)
- [x] Additional data extraction (using embedding and LLM):
  - Extract basic shares outstanding for the specific time period
  - Extract diluted shares outstanding for the specific time period
  - Extract amortization for the specific time period (for quarterly/annual filings)
  - Extract unit of measurement for each additional item (revenue_prior_year, shares outstanding, amortization)
- [x] **GAAP/EBITDA Reconciliation Extraction (Earnings Announcements Only):**
  - Separate GAAP reconciliation extractor from amortization extractor (exclusive to earnings announcements)
  - Use dedicated `agents/gaap_reconciliation_extractor.py` with chunk-based embedding search
  - Search for "GAAP reconciliation" or "EBITDA reconciliation" tables (ignore first 50% of chunks, search in second 50%)
  - Extract amortization and other reconciliation line items from these tables
  - Add comprehensive logging for GAAP reconciliation extraction (similar to balance sheet and income statement)
  - Earnings announcements use GAAP reconciliation extractor and do NOT use the amortization extractor
- [x] Validation and error handling (see sections 5.5 and 5.6 for two-stage validation details):
  - Stage 1 validation: LLM completeness check on chunk text (validates chunk contains complete income statement before extraction)
  - Stage 2 validation: Post-process and validate using final_diff logic (checks gross profit, operating income, and other calculations during normalization)
  - LLM feedback loop: If post-processing validation fails, retry extraction with validation errors, calculated differences, and cost normalization explanation included in prompt
- [x] Line item classification:
  - Use LLM to categorize each income statement line item as operating or non-operating
  - LLM should use best judgment for classification
- [x] Data persistence and display:
  - Persist income statement extraction
  - Persist line item classification
  - Persist revenue growth calculation (year-over-year)
  - Persist shares outstanding (basic and diluted)
  - Persist amortization
  - Display all income statement data in right panel when document is selected in left panel
  - Display "Additional Items" table with: prior period revenue, YOY revenue growth, amortization, basic shares outstanding, diluted shares outstanding
- [x] Real-time progress tracking:
  - Async progress tracking with polling
  - Milestone tracking: extracting balance sheet, classifying balance sheet, extracting income statement, extracting additional items, classifying income statement
  - Status display in right panel with real-time updates
  - Combined tracker showing all 5 milestones with status: checking, pending, in_progress, completed, error, not_found
  - Progress tracker shows first, financial statements load only when all milestones are terminal
- [x] Re-run functionality:
  - Single "Re-run Extraction and Classification" button that re-runs entire pipeline
  - Button immediately sets all milestones to pending and starts polling
  - Button disabled during processing
- [x] Delete functionality:
  - "Delete Financial Statements" button to remove all financial statement data
  - "Delete Document" button that permanently deletes document and all associated data

#### 5.3: Historical Calculations (Complete)
All calculations are performed for a specific document using the extracted balance sheet and income statement items.

- [x] **Net Working Capital Calculation**
  - Sum all Current Assets labeled as Operating
  - Sum all Current Liabilities labeled as Operating
  - Calculate: Net Working Capital = Current Assets Operating - Current Liabilities Operating

- [x] **Net Long Term Operating Assets Calculation**
  - Sum all Non-current Assets labeled as Operating
  - Sum all Non-current Liabilities labeled as Operating
  - Calculate: Net Long Term Operating Assets = Non-current Assets Operating - Non-current Liabilities Operating

- [x] **Invested Capital Calculation**
  - Calculate: Invested Capital = Net Working Capital + Net Long Term Operating Assets

- [x] **Capital Turnover Calculation**
  - Calculate: Capital Turnover = Revenue / Invested Capital
  - For quarterly statements (Q1, Q2, Q3, Q4): Annualize revenue by multiplying by 4 before calculation
  - For fiscal year statements (FY): Use revenue as-is
  - Displayed as "Capital Turnover, Annualized" in the UI

- [x] **EBITA Calculation**
  - Take Operating Income, which could be called other names such as income from operations, from income statement
  - Subtract all items between Operating Income and Revenue that are labeled as Non-Operating
  - Subtract Amortization if available and not already subtracted
  - Calculate: EBITA = Operating Income - Non-Operating Items - Amortization

- [x] **EBITA Margin Calculation**
  - Calculate: EBITA Margin = EBITA / Revenue

- [x] **Effective Tax Rate Calculation**
  - Try multiple methods depending on what is available in the income statement
  - Calculate using available tax information (income tax expense, provision for income taxes, etc.)

- [x] **Display and Recalculation**
  - Display all calculated metrics as a table in the right panel in a new section called "Historical Calculations"
  - Display unit for each metric (monetary values use balance sheet/income statement unit, ratios/percentages show "—")
  - Add a "Re-run Historical Calculations" button in the left panel, in the Re-run Processing section
  - Button triggers recalculation of all historical calculations using the latest extracted balance sheet and income statement data
  - Historical calculations automatically trigger after income statement classification completes
  - Unit is persisted and displayed for all monetary metrics

#### 5.4: Enhanced Historical Calculations with LLM Intelligence (Complete, except Adjusted Tax Rate)
- [x] **LLM-Enhanced Operating Income Identification** (Complete)
  - Implemented via `get_income_statement_llm_insights` and `post_process_income_statement_line_items`
  - LLM intelligently identifies operating income using various naming conventions (e.g., "income from operations", "operating income", "operating profit")
  - Line items are renamed with standardized names (e.g., "Operating Income (Income from Operations)") for consistent processing
  - Improves accuracy of operating income extraction for EBITA calculations

- [x] **LLM-Enhanced Tax-Related Item Identification** (Complete)
  - Implemented via `get_income_statement_llm_insights` and `extract_tax_inputs`
  - LLM identifies pretax income, tax expenses, and net income using standardized names
  - Handles various naming conventions for tax-related line items
  - Functions prioritize standardized names (e.g., "Pretax Income (Income Before Tax)", "Tax Expense (Provision for Income Taxes)")
  - Improves accuracy of effective tax rate calculations

- [x] **Cost Format Normalization** (Complete)
  - Implemented via `post_process_income_statement_line_items`
  - Automatically detects whether costs are stored as positive or negative in the document
  - Normalizes all costs to negative format (standard accounting convention)
  - Handles edge cases like missing gross profit or operating income
  - Preserves benefits/credits as positive values

- [x] **LLM-Enhanced Non-Operating Item Identification** (Complete)
  - Line items are classified as operating or non-operating during the classification step
  - Classification uses LLM-based categorization in `classify_line_items_llm`
  - Non-operating items are used in EBITA and adjusted tax rate calculations

#### 5.5: Updated Balance Sheet and Income Statement Validation (Complete)
- [x] Refactored validation logic to separate section finding from extraction/validation with a two-stage retry mechanism
- [x] **Balance Sheet Processing:**
  - Stage 1: Find Balance Sheet Section
    - Use rank 1 chunk (best match) to locate balance sheet section
    - Attempt extraction using LLM
    - Validate by checking minimum line count (10 lines) and presence of key lines
    - If validation fails, retry with rank 2 chunk, then rank 3 chunk (3 tries total for finding)
    - Once section validation succeeds, proceed to Stage 2
  - Stage 2: Validate Extraction Calculations
    - Validate sums (current assets, total assets, current liabilities, total liabilities, balance sheet equation)
    - If validation fails:
      - Calculate and report differences in error messages
      - Pass section text, extracted table, and validation errors to LLM for correction
      - Retry extraction up to 3 times total (including initial attempt)
      - Each retry includes full error context to help LLM correct mistakes
- [x] **Income Statement Processing:**
  - Stage 1: Find Income Statement Section
    - Use chunk immediately before balance sheet chunk to locate income statement
    - Attempt extraction using LLM
      - Validate by checking minimum line count (5 lines) and presence of required items (Total Net Revenue, Net Income)
      - Line items can be categorized as "Recurring", "One-Time", or "Total"
      - Total line items (e.g., "Total Net Revenue", "Total Expenses") are excluded from validation sum calculations to avoid double counting
      - Total line items do not have `is_operating` classification (except "Total Net Revenue" which is operating)
    - If validation fails, retry with chunk after balance sheet, then 2 chunks after balance sheet (3 tries total for finding)
    - Once section validation succeeds, proceed to Stage 2
  - Stage 2: Post-Process and Validate Extraction
    - Post-process line items (normalize cost format, identify key items)
    - Validate using final_diff logic (checks calculations during normalization)
    - If validation fails:
      - Calculate and report differences in error messages
      - Pass section text, extracted table, explanation about cost normalization, and validation errors to LLM for correction
      - Retry extraction up to 3 times total (including initial attempt)
      - Each retry includes full error context and normalization explanation
- [x] **Key Improvements:**
  - Clear separation between section finding and extraction validation
  - Two-stage retry mechanism reduces false positives from wrong sections
  - LLM feedback loop includes calculation differences for better correction
  - More robust handling of edge cases and extraction errors

#### 5.6: Further Updates to Balance Sheet and Income Statement Validation (Complete)
- [x] **LLM Completeness Checks (Before Extraction)**
  - Added completeness checks that validate chunk text BEFORE extraction to avoid wasting tokens
  - Balance sheet: Ask LLM if chunk contains a complete consolidated balance sheet starting from cash to total shareholder's equity (uses full chunk text, not truncated)
  - Income statement: Ask LLM if chunk contains a complete consolidated income statement starting from revenue to net income (uses full chunk text, not truncated)
  - Completeness checks avoid smaller informational tables that don't have complete information
  - Updated processing flow: Find chunk → Check completeness (on full chunk text) → Extract → Normalize & Classify → Stage 2 validation
- [x] **Standard Names for Balance Sheet Key Items**
  - Added standard names for key balance sheet line items (similar to income statement)
  - Standard names include: Cash & Equivalents, Other Current Assets, Total Current Assets, Other Non-Current Assets, Other Current Liabilities, Total Current Liabilities, Other Non-Current Liabilities, Total Liabilities, Total Shareholder's Equity
  - Original names preserved in parentheses (e.g., "Cash & Equivalents (Cash and cash equivalents)")
  - Implemented via `get_balance_sheet_llm_insights()` and `post_process_balance_sheet_line_items()`
- [x] **Stage 2 Validation Preserved**
  - Kept Stage 2 validation logic as requested (calculation validation for balance sheet, post-processing validation for income statement)
  - Balance sheet: Validates sums (current assets, total assets, current liabilities, total liabilities, balance sheet equation) with retries
  - Income statement: Post-processes and validates using final_diff logic with retries
- [x] **Chunk Index Persistence**
  - Added `chunk_index` field to `BalanceSheet` and `IncomeStatement` database models
  - Chunk index persisted after successful extraction for traceability and observability
  - Enables tracking which chunk was used for each financial statement extraction
  - Migration script created: `migrate_add_chunk_index_fields.py`

### Phase 6: Company Analysis and Adjustments

#### Context for Phases 6.2-6.8: Implementation Architecture and Patterns

**Key Architecture Patterns:**
- **Agent Pattern**: Each extraction agent is a standalone module in `agents/` (e.g., `balance_sheet_extractor.py`, `income_statement_extractor.py`). Agents use LLM calls via `generate_content_safe()` from `app/utils/gemini_client.py` with `temperature=0.0` for extraction tasks to prevent hallucination.
- **Document Section Finding**: Use `find_document_section()` from `app/utils/document_section_finder.py` to search for relevant chunks. Parameters: `query_texts` (list of search terms), `pages_before=0`, `pages_after=0` (for exact chunk text), `rerank_top_k=5` (re-rank top 5 chunks), `rerank_query_texts` (optional list for re-ranking). The function returns `(text, start_page, log_info)` or `(None, None, None)`.
- **Progress Tracking**: Use `FinancialStatementMilestone` enum and progress tracking functions from `app/utils/financial_statement_progress.py`. Call `update_milestone()` to update status, `add_log()` for progress logs. Status values: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `ERROR`, `NOT_FOUND`.
- **Database Models**: SQLAlchemy models in `app/models/`. Follow existing patterns: `BalanceSheet`, `BalanceSheetLineItem`, `IncomeStatement`, `IncomeStatementLineItem`. Use `Numeric(20, 2)` for monetary values, `String` for text, nullable fields where appropriate. Include `document_id` foreign key, timestamps, validation flags.
- **Router Pattern**: FastAPI routers in `app/routers/`. Use background tasks for async processing. Follow pattern in `balance_sheet.py` and `income_statement.py`: async processing function, progress tracking, error handling, database commits.
- **Standardized Naming**: Balance sheet and income statement extractors use `get_*_llm_insights()` to identify key line items, then `post_process_*_line_items()` to rename them. Standard names format: `"Standard Name (Original Name)"` - original name preserved in parentheses. Example: `"Cash & Equivalents (Cash and cash equivalents)"`.
- **Chunk Index Persistence**: Store `chunk_index` (Integer, nullable) in database models for traceability. The chunk index indicates which document chunk (0-based) was used for extraction.
- **LLM Prompt Patterns**: Include `CRITICAL ANTI-HALLUCINATION RULES` in prompts. Use structured JSON output. Specify exact field names and formats. Use `temperature=0.0` for all extraction tasks.
- **Validation Patterns**: Two-stage validation: Stage 1 (completeness/section validation) happens before extraction; Stage 2 (calculation/consistency validation) happens after extraction. Use retry logic with different chunk ranks or with error feedback to LLM.
- **Unit Handling**: Each monetary value should have a unit field (String, nullable). Units: `"ones"`, `"thousands"`, `"millions"`, `"billions"`, `"ten_thousands"`. Extract units from document notes using LLM.

**Existing Code References:**
- Balance sheet extraction: `agents/balance_sheet_extractor.py` - see `extract_balance_sheet()`, `check_balance_sheet_completeness_llm()`, `get_balance_sheet_llm_insights()`, `post_process_balance_sheet_line_items()`
- Income statement extraction: `agents/income_statement_extractor.py` - see `extract_income_statement()`, `extract_additional_data_llm()` (currently extracts amortization, shares outstanding)
- Progress tracking: `app/utils/financial_statement_progress.py` - see `FinancialStatementMilestone` enum, `update_milestone()`, `add_log()`
- Document section finding: `app/utils/document_section_finder.py` - see `find_document_section()`
- Router patterns: `app/routers/balance_sheet.py`, `app/routers/income_statement.py`
- Database models: `app/models/balance_sheet.py`, `app/models/income_statement.py`
- Historical calculations: `app/routers/historical_calculations.py`, `app/models/historical_calculation.py`

**Data Flow Pattern:**
1. Document indexing completes → triggers financial statement processing
2. Balance sheet extraction → income statement extraction → additional items extraction (currently in income statement extractor)
3. Each extraction: find section → completeness check → extract → normalize/classify → validate → persist
4. Progress tracked via milestones, displayed in frontend via polling

**Future State (After Phase 6.2-6.8):**
- Additional items separated into their own extraction agents
- New database models for: organic growth, other assets, other liabilities, non-operating asset classification
- Separate progress milestones for each additional item type
- Historical calculations UI reorganized into sections (Invested Capital, Adjusted Tax Rate, EBITA, NOPAT & ROIC) plus summary table

#### 6.1: Historical Calculations Table for Company View (Complete)
- [x] **Company-Level Historical Calculations Display**
  - Show collected table of historical calculations from all earnings announcements for the selected company (quarterly/annual filings not yet implemented)
  - Columns: Time periods (de-duplicated and in ascending order, with most recent report on the right)
  - Display Currency and Unit above the table (with note that units do not apply to percentages and ratios)
  - Rows in order:
    1. Revenue
    2. YOY Revenue Growth
    3. EBITA
    4. EBITA Margin
    5. Effective Tax Rate
    6. Adjusted Tax Rate
    7. Net Working Capital
    8. Net Long Term Operating Assets
    9. Invested Capital
    10. Capital Turnover, Annualized
  - Display in right panel when a company is selected (currently blank)
  - Aggregate data from all eligible documents (earnings announcements) for the company (quarterly/annual filings not yet implemented)

#### 6.2: Major Refactor for Additional Items and Historical Calculations Structure (Complete)
**Goal**: Separate additional items extraction from income statement extractor and reorganize historical calculations UI structure.

**Backend Refactoring:**
- [x] Extract additional items logic from `agents/income_statement_extractor.py`. The `extract_additional_data_llm()` function currently extracts amortization and shares outstanding - these should be moved to dedicated agents.
- [x] Create new agent modules in `agents/` for each additional item type (see sections 6.3-6.8 below). Each agent should follow the pattern: find section → completeness check → extract → validate → return structured data.
- [x] Create database models in `app/models/` for new data structures: organic growth, other assets line items, other liabilities line items, non-operating asset classifications. Follow existing patterns from `BalanceSheetLineItem` and `IncomeStatementLineItem`.
- [x] Create new routers in `app/routers/` for each additional item type, or a unified `additional_items.py` router with endpoints for each type. Follow the async processing pattern from balance sheet and income statement routers.
- [x] Update progress tracking in `app/utils/financial_statement_progress.py`: Add new milestones for each additional item type (or consolidate into milestone groups). Update `initialize_progress()` and reset functions to include new milestones.
- [x] Create Pydantic schemas in `app/schemas/` for request/response models for each additional item type.
- [x] Consolidate milestone tracking to 4 main milestones (down from 10+ separate milestones):
  1. **Balance Sheet** (combines extracting + classifying balance sheet into single milestone)
  2. **Income Statement** (combines extracting + classifying income statement into single milestone)
  3. **Extracting Additional Items** (combines organic growth, amortization, other assets, other liabilities, shares outstanding into single milestone with sub-item logging)
  4. **Classifying Non-Operating Items** (unchanged)
- [x] Update pipeline execution order in `app/utils/document_processing_queue.py` to match the new milestone order
- [x] For "Extracting Additional Items" milestone: add logging via `add_log()` to show which sub-items (organic growth, amortization, etc.) are being processed/completed

**Frontend Scaffolding:**
- [x] Create placeholder components in `frontend/src/components/` for displaying each additional item type (organic growth table, amortization table, other assets table, etc.).
- [x] Update `RightPanel.jsx` to include new sections for additional items. Structure should allow for each item type to be displayed independently.
- [x] Create placeholder API integration functions for fetching each additional item type.
- [x] Review and fix CSS spacing/padding in `frontend/src/components/RightPanel.css` to restore proper table layout
- [x] Remove "Revenue Context" table/section from `frontend/src/components/RightPanel.jsx` (redundant with Organic Growth table)
- [x] Update `OtherAssetsTable` and `OtherLiabilitiesTable` components:
  - Display standardized line items with standardized names as reference (similar to balance sheet format)
  - Modify de-duplication logic to exclude line items that match/duplicate the total lines
  - Goal: Show what composes the "Other Assets/Liabilities" totals
- [x] Improve formatting in `NonOperatingClassificationTable` component:
  - Enhance text formatting/styling for Category and Source columns
  - Add "common_equity" to the category enum/options (update backend model if needed)
  - Reference UI patterns from other table components for consistency

**Historical Calculations UI Reorganization:**
- [x] The existing historical calculations table (section 6.1) becomes the "Summary Table" at the bottom of the historical calculations section.
- [x] Add "Organic Growth" row above "EBITA" in the summary table.
- [x] Change "Effective Tax Rate" label to "Adjusted Tax Rate" in the summary table.
- [ ] Create new sections above the summary table (in order from top to bottom):
  1. **Invested Capital Section**: Display components/calculations related to invested capital adjustments
  2. **Adjusted Tax Rate Section**: Display components/calculations related to adjusted tax rate (currently calculated, but will need breakdown)
  3. **EBITA Section**: Display components/calculations related to EBITA adjustments
  4. **NOPAT & ROIC Section**: Display NOPAT and ROIC calculations and components
- [x] Summary Table: Display at the bottom with all time periods as columns, metrics as rows (including new Organic Growth row, Adjusted Tax Rate label change).

**Configuration and Code Quality:**
- [x] Update `ignore_front_fraction` and `ignore_back_fraction` parameter defaults to `0.0` (currently may default to None or non-zero)
- [x] Add standardized names for: "Common Equity", "Total Equity", "Total Liabilities" in balance sheet extractor
- [x] Update balance sheet post-processing logic: ensure that total/subtotal lines do NOT have an `is_operating` classification (should be `None` or excluded)

#### 6.3: Organic Growth Extraction (Complete)
**Goal**: Extract organic growth data by identifying acquisitions and their revenue impact, then calculating organic revenue growth.

**Implementation Approach:**
- [x] Create `agents/organic_growth_extractor.py` following the pattern from balance sheet/income statement extractors.
- [x] Use `find_document_section()` with query texts: `["merge", "acquire", "acquisition", "m&a"]`. Set `pages_before=0`, `pages_after=0` to get exact chunk text (no page padding). Use `rerank_top_k=3` to get top 3 chunks, then concatenate them.
- [x] Create LLM extraction function that takes the concatenated text and time period. The prompt should:
  - Ask if the company made an acquisition within the year that affects this time period's revenue
  - Extract the revenue impact amount (zero if no acquisition)
  - Use `temperature=0.0` and include anti-hallucination rules - only extract information explicitly stated in the text
  - Return structured JSON with: acquisition flag (boolean), revenue impact (numeric, can be zero), unit (extracted from document notes)
- [x] Database model in `app/models/organic_growth.py`: Store `document_id`, `time_period`, `prior_period_revenue`, `prior_period_revenue_unit`, `current_period_revenue`, `current_period_revenue_unit`, `simple_revenue_growth` (percentage), `acquisition_revenue_impact`, `acquisition_revenue_impact_unit`, `current_period_adjusted_revenue`, `current_period_adjusted_revenue_unit`, `organic_revenue_growth` (percentage), `chunk_index`, timestamps, validation flags.
- [x] Calculation logic: 
  - Prior period revenue comes from income statement (revenue_prior_year field)
  - Current period revenue comes from income statement (total revenue)
  - Simple revenue growth = (current - prior) / prior * 100
  - Current period adjusted revenue = current period revenue - acquisition revenue impact
  - Organic revenue growth = (adjusted - prior) / prior * 100 (equals simple growth if no acquisition impact)
- [x] Create router endpoint following pattern from balance sheet/income statement routers. Trigger after income statement extraction completes.
- [x] Progress tracking: Log organic growth under the consolidated `EXTRACTING_ADDITIONAL_ITEMS` milestone.
- [x] Frontend: Create component to display organic growth table with all fields, formatted appropriately (percentages as percentages, monetary values with units).

#### 6.4: Amortization Extraction (Refactor from Income Statement) (Complete)
**Goal**: Extract all amortization line items from the document, categorize them as operating or non-operating, and store them separately from income statement data.

**Implementation Approach:**
- [x] Extract amortization logic from `agents/income_statement_extractor.py` (currently in `extract_additional_data_llm()`). Create new `agents/amortization_extractor.py`.
- [x] Use `find_document_section()` with query texts: `["amortize", "amortization"]`. Set `pages_before=0`, `pages_after=0`, `rerank_top_k=3`, concatenate top 3 chunks.
- [x] Create LLM extraction function that:
  - Identifies all amortization line items for the time period (name and value)
  - Categorizes each as operating or non-operating based on examples:
    - Non-operating: amortization of acquired intangibles, amortization of financing costs
    - Operating: amortization of capitalized sales costs, amortization of capitalized software
  - Uses `temperature=0.0` with strict anti-hallucination rules
  - Returns JSON array of line items with: `line_name`, `line_value`, `unit`, `is_operating` (boolean), `category` (string: "operating" or "non-operating")
- [x] Database model in `app/models/amortization.py`: Create `Amortization` (parent) and `AmortizationLineItem` (child) tables. `Amortization` stores `document_id`, `time_period`, `currency`, `chunk_index`, timestamps. `AmortizationLineItem` stores `amortization_id`, `line_name`, `line_value`, `unit`, `is_operating`, `category`, `line_order`.
- [x] Validation: Deduplicate line items by name (case-insensitive, normalized). If duplicates found, log warning and keep one instance (prefer the one with more complete information).
- [x] Create router endpoint. Trigger after income statement extraction completes (can run in parallel with organic growth if desired, but sequential is safer for API rate limiting).
- [x] Progress tracking: Log amortization under the consolidated `EXTRACTING_ADDITIONAL_ITEMS` milestone.
- [x] Frontend: Create component to display amortization line items table with columns: Line Name, Value, Unit, Type (Operating/Non-operating). Group by type or use visual indicators.

#### 6.5: Other Assets Extraction and Classification (Complete)
**Goal**: Extract detailed line items within "Other Current Assets" and "Other Non-Current Assets" from the balance sheet, and classify each as operating or non-operating.

**Implementation Approach:**
- [x] Create `agents/other_assets_extractor.py`. This agent requires the balance sheet to already be extracted (to get the standardized names).
- [x] Retrieve balance sheet line items from database for the document. Find line items with standardized names "Other Current Assets" or "Other Non-Current Assets". Extract the original names from parentheses (e.g., if standardized name is "Other Current Assets (Other current assets, net)", use "Other current assets, net" as the search term).
- [x] Use `find_document_section()` with query texts set to the original names from the balance sheet (for both other current assets and other non-current assets). Set `pages_before=0`, `pages_after=0`, `rerank_top_k=3`, concatenate top 3 chunks.
- [x] Create LLM extraction function that:
  - Takes the concatenated text, time period, and the total values from balance sheet (for validation)
  - Identifies all line items within other current assets and other non-current assets for the time period
  - For each line item, extracts: `line_name`, `line_value`, `unit`, `category` ("Current Assets" or "Non-Current Assets")
  - Classifies each as operating or non-operating:
    - Non-operating examples: financial derivatives, currency hedges, investments, marketable securities
    - Operating: everything else (the default assumption for other assets is operating unless explicitly financial)
  - Uses `temperature=0.0` with strict anti-hallucination rules
  - Returns JSON with line items array and validation totals
- [x] Validation logic:
  - Deduplicate line items by name (case-insensitive, normalized)
  - Sum line items for "Other Current Assets" and compare with balance sheet total
  - Sum line items for "Other Non-Current Assets" and compare with balance sheet total
  - If sums don't match (within small tolerance, e.g., 0.01% or $1000), retry LLM extraction with error feedback asking it to verify the time period is correct and check for missing line items
- [x] Database model in `app/models/other_assets.py`: Create `OtherAssets` (parent) and `OtherAssetsLineItem` (child) tables. `OtherAssets` stores `document_id`, `time_period`, `currency`, `chunk_index`, validation flags. `OtherAssetsLineItem` stores `other_assets_id`, `line_name`, `line_value`, `unit`, `is_operating`, `category` ("Current Assets" or "Non-Current Assets"), `line_order`.
- [x] Create router endpoint. Trigger after balance sheet extraction and classification completes.
- [x] Progress tracking: Log other assets extraction under the consolidated `EXTRACTING_ADDITIONAL_ITEMS` milestone.
- [x] Frontend: Create component to display other assets line items table. Show columns: Line Name, Value, Unit, Category (Current/Non-Current), Type (Operating/Non-operating). Allow filtering/grouping by category and type.

#### 6.6: Other Liabilities Extraction and Classification (Complete)
**Goal**: Extract detailed line items within "Other Current Liabilities" and "Other Non-Current Liabilities" from the balance sheet, and classify each as operating or non-operating. Follow the same pattern as Other Assets (section 6.5).

**Implementation Approach:**
- [x] Create `agents/other_liabilities_extractor.py` following the same structure as `other_assets_extractor.py`.
- [x] Retrieve balance sheet line items. Find standardized names "Other Current Liabilities" and "Other Non-Current Liabilities", extract original names from parentheses.
- [x] Use `find_document_section()` with original names as query texts. Set `pages_before=0`, `pages_after=0`, `rerank_top_k=3`, concatenate top 3 chunks.
- [x] Create LLM extraction function similar to other assets:
  - Identifies all line items within other current liabilities and other non-current liabilities
  - Classifies as operating or non-operating (default to operating unless explicitly financial)
  - Non-operating examples: financial derivatives, currency hedges, investment-related liabilities
- [x] Same validation logic: deduplicate, sum validation against balance sheet totals, retry with error feedback if mismatch.
- [x] Database model in `app/models/other_liabilities.py`: Same structure as other assets, with `category` values "Current Liabilities" or "Non-Current Liabilities".
- [x] Create router endpoint. Trigger after balance sheet extraction completes (can run in parallel with other assets, but sequential is safer).
- [x] Progress tracking: Log other liabilities extraction under the consolidated `EXTRACTING_ADDITIONAL_ITEMS` milestone.
- [x] Frontend: Create component similar to other assets component, displaying other liabilities line items with appropriate columns and filtering.

#### 6.7: Shares Outstanding Extraction (Refactor from Income Statement) (Complete)
**Goal**: Extract basic and diluted shares outstanding from the document. Currently extracted in income statement extractor, should be moved to dedicated agent.

**Implementation Approach:**
- [x] Extract shares outstanding logic from `agents/income_statement_extractor.py` (currently in `extract_additional_data_llm()`). Create new `agents/shares_outstanding_extractor.py`.
- [x] Use `find_document_section()` with query texts: `["weighted average", "shares", "basic", "diluted"]`. Set `pages_before=0`, `pages_after=0`, `rerank_top_k=3`, concatenate top 3 chunks.
- [x] Create LLM extraction function that:
  - Identifies basic shares outstanding and diluted shares outstanding for the time period
  - Extracts values and units (usually "ones" for share counts)
  - Uses standardized field names: "Basic Shares Outstanding" and "Diluted Shares Outstanding"
  - Uses `temperature=0.0` with strict anti-hallucination rules
  - Returns JSON with: `basic_shares_outstanding`, `basic_shares_outstanding_unit`, `diluted_shares_outstanding`, `diluted_shares_outstanding_unit`
- [x] Database model: Can reuse `IncomeStatement` model fields (since shares outstanding is already stored there), or create new `app/models/shares_outstanding.py` if we want to separate it completely. For now, keeping in income statement model is acceptable, but the extraction logic should be in a separate agent.
- [x] Create router endpoint or integrate into existing additional items router. Trigger after income statement extraction completes.
- [x] Progress tracking: Log shares outstanding extraction under the consolidated `EXTRACTING_ADDITIONAL_ITEMS` milestone.
- [x] Frontend: Can continue displaying in income statement section, or move to separate additional items section. Display as table with: Metric (Basic/Diluted), Value, Unit.

#### 6.8: Non-Operating Asset Classification (Complete)
**Goal**: Classify all non-operating items from balance sheet, other assets, and other liabilities into detailed categories for valuation adjustments.

**Implementation Approach:**
- [x] Create `agents/non_operating_classifier.py`. This agent requires balance sheet, other assets, and other liabilities to be already extracted.
- [x] Collect all non-operating line items from:
  - Balance sheet line items where `is_operating = False`
  - Other assets line items where `is_operating = False`
  - Other liabilities line items where `is_operating = False`
- [x] Deduplicate items by name (case-insensitive, normalized) across all three sources. If the same item appears in multiple sources, keep one instance with the most complete information.
- [x] Create LLM classification function that:
  - Takes the deduplicated list of non-operating items (line name, value, unit, source)
  - Classifies each item into one of these categories:
    - `cash`: Cash and cash equivalents, restricted cash
    - `short_term_investments`: Marketable securities, short-term investments
    - `operating_lease_related`: Operating lease assets/liabilities
    - `other_financial_physical_assets`: Assets held for sale, other financial assets, physical assets not used in operations
    - `debt`: Loans, notes payable, bonds, other debt
    - `other_financial_liabilities`: Financial derivatives, currency hedges (liabilities), other financial liabilities
    - `deferred_tax_assets`: Deferred tax assets
    - `deferred_tax_liabilities`: Deferred tax liabilities
    - `preferred_equity`: Preferred stock, preferred shares
    - `minority_interest`: Non-controlling interest, minority interest
    - `goodwill_intangibles`: Goodwill, intangible assets (acquired)
    - `unknown`: Items that don't fit the above categories
  - Uses `temperature=0.0` with strict anti-hallucination rules
  - Returns JSON array with items and their classifications
- [x] Database model in `app/models/non_operating_classification.py`: Create `NonOperatingClassification` (parent) and `NonOperatingClassificationItem` (child) tables. `NonOperatingClassification` stores `document_id`, `time_period`, timestamps. `NonOperatingClassificationItem` stores `classification_id`, `line_name`, `line_value`, `unit`, `category` (one of the categories above), `source` ("balance_sheet", "other_assets", "other_liabilities"), `line_order`.
- [x] Create router endpoint. Trigger after balance sheet, other assets, and other liabilities extractions complete.
- [x] Progress tracking: Keep the `CLASSIFYING_NON_OPERATING_ITEMS` milestone for non-operating classification.
- [x] Frontend: Create component to display non-operating classification table. Show columns: Line Name, Value, Unit, Category, Source. Allow filtering/grouping by category and source. Use color coding or icons for different categories.

#### 6.9: Invested Capital
- [x] **Net Working Capital**: Updated formula to exclude "Total" and "Subtotal" line items to prevent double-counting.
- [x] **Net Long Term Operating Assets**: Updated formula to exclude "Total" and "Subtotal" line items to prevent double-counting.

#### 6.10: Adjusted Tax Rate
- [ ] TBD

#### 6.11: EBITA
- [ ] TBD

#### 6.12: NOPAT and ROIC
- [ ] TBD

### Phase 7: UI Standardization and Refinement (Complete)

#### 7.1: Button Logic & UI Interaction Standardization
- [x] **Define and Implement Button State Rules**:
  - **Initial State**: Buttons should load quickly but start in a `disabled` state if dependencies are not met.
  - **Enable Condition**: Buttons become `enabled` only after specific conditions (e.g., file loaded, processing complete) are met.
  - **Click Behavior**: Upon click, the button must significantly and immediately transition to a `disabled` state to prevent double-submissions.
  - **Cross-Component Signaling**: Clicking a button should trigger disabling of other relevant buttons *immediately* via state push (e.g., using a global context or event), rather than waiting for valid polling or asynchronous status updates.
  - **Re-enable Logic**: Buttons should re-enable via explicit "push" logic (e.g., completion event received) rather than relying solely on passive polling.
- [x] **Documentation**: Updated `UI_UX_DESIGN.md` with these standardized button behavior guidelines.

#### 7.2: Fine-Tuning UI Elements
**General Tables & Views**:
- [x] **Loading Optimization**: In the Document Detail View, ensure the **Raw Document (PDF Viewer)** loads *last* (or asynchronously without blocking) so the critical financial data/tables appear first.
- [x] **Non-GAAP Reconciliation**: Remove the "Category" column from the table.
- [x] **Table Headers**: Add "Time Period" as the first item in the header for: Shares Outstanding, Non-GAAP Reconciliation, Organic Growth, Non-Operating Classification, Historical Calculations.

**Summary & Historical Calculations Section**:
- [x] **Summary Table Metadata**: Added "Time Period", "Currency", and "Unit" fields to the Summary Table.
- [x] **Dividers**: Adjusted dividers for better visual separation between detailed breakdowns and summary tables.
- [x] **Titles**: Removed redundant table titles within the Historical Calculations section for cleaner UI.
- [x] **Layout**: Moved "Adjusted Tax Rate" section to be below the Invested Capital/EBITA sections.
- [x] **Design Compliance**: Audited Historical Calculations section for `UI_UX_DESIGN.md` compliance.

### Phase 8: Financial Modeling
- [ ] TBD

### Phase 9: App-wide Analysis and Dashboard (right panel of the Top-level page)
- [ ] TBD

### Phase 10: Refactor app to focus on company -> time period -> documents, enable incorporating other documents
- [ ] TBD

### Phase 11: Get transcripts, news, and analyst repots to work to provide additional insights.
- [ ] TBD

### Phase 12: Get 10-K and 10-Q to provide additional details.
- [ ] Other assets
- [ ] Other liabilities
- [ ] Organic growth, improved

## Next Steps

### Immediate Priorities
- [ ] Change the first column header in the Organic Growth table from Metric to Line Item
- [ ] Fix the Historical Calculations table formatting according the UI_UX_DESIGN.md and what the Balance Sheet and Income Statement tables look like
- [ ] Fix the Net Working Capital calculation and frontend display - First Collect all the Current Assets that are Operating. Then collect all the Current Liabilities that are Operating. Subtract the two subtotals. Currently, it looks like the app is not able to collect the Current Liabilities that are Operating.
- [ ] Fix the Net Long Term Operating Assets calculation and frontend display - First Collect all the non-current assets that are operating. Then collect all the non-current liabilities that are operating. Then subract the two subtotals. Currently, it looks like ht app is not able to collect the Non-current liabilities that are Operating.
- [ ] Make the Net Working Capital, Net Long Term Operating Assets, and Invested Capital tables closer together. They go together. Make the EBITA, NOPAT and ROIC, and Adjusted Tax Rate tables closer together. They go together.
- [ ] Move the NOPAT and ROIC table to below the Adjusted Tax Rate table.
- [ ] Fix the Summary Table formtating according to UI_UX_DESIGN.md


### Backlog / Future Enhancements
- [ ] **Tagging System**: Replace "Type", "Category", and "Status" columns with a unified **Tagging System**.
  - Single "Tag" column supporting multiple simultaneous tags (e.g., "Operating", "Recurring", "Non-Cash").
  - Status fields becomes a tag (e.g., "Indexed", "Balance Sheet").
- [ ] **UI Interactivity**: Implementation capability to change "Category" and "Type" directly in the UI.

## UI/UX Design

For detailed UI/UX specifications and design guidance, see [UI_UX_DESIGN.md](UI_UX_DESIGN.md).