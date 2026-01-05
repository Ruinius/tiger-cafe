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
6. Index document using Google's embedding model (gemini-embedding-001)
   - Documents are split into 2-page chunks for indexing
   - Chunk embeddings are generated and persisted to disk
   - Classification and indexing happen sequentially via priority queue (high priority)
   - Upload step is parallel, but classification/indexing are sequential
7. After indexing completes, automatically trigger financial statement processing (for eligible document types):
   - Financial statement processing is queued with lower priority
   - Classification/indexing tasks are always processed before financial statement extraction
   - Balance sheet extraction and classification (runs first)
   - Income statement extraction, additional items extraction, and classification (runs after balance sheet completes)
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
5. Financial statement processing (balance sheet and income statement) is automatically triggered sequentially after document indexing completes (for eligible document types)
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
  - Statuses: PENDING, UPLOADING, CLASSIFYING, INDEXING, INDEXED, ERROR
  - Duplicate detection flags (duplicate_detected, existing_document_id)
- [x] Real-time status updates (polling mechanism)
- [x] Progress indicators for indexing/processing (in upload progress view and document list)
- [x] Document summary persistence and display
  - Summary generated during initial upload (LLM-based)
  - Displayed in document detail view and upload workflow

### Phase 5: Financial Statement Processing

#### 5.1: Balance Sheet Processing (Complete)
- [x] Automatic trigger: Balance sheet processing automatically starts after document indexing completes (for earnings announcements, quarterly filings, and annual reports only)
- [x] Sequential processing: Balance sheet and income statement processing run sequentially (not in parallel) to avoid overwhelming Gemini API
- [x] Use persisted chunk embeddings to locate the consolidated balance sheet section
  - Reuses chunk embeddings generated during document indexing
  - No duplicate embedding generation during extraction
  - Efficient chunk-level embedding search for precise location
  - Document type-based search range restrictions:
    - Earnings announcement: ignore first 30% and last 10% of document
    - Annual filing: ignore first 50% and last 20% of document
    - Quarterly filing: ignore last 50% of document (no front ignore)
  - Two-stage validation with retry strategy (see section 5.5 for details):
    - Stage 1: Try rank 1, 2, 3 chunks to find correct section (validates line count + key lines)
    - Stage 2: Retry extraction up to 3 times with LLM feedback if sum validation fails
- [x] LLM-based extraction of balance sheet line items:
  - Extract balance sheet exactly line by line for the specified time period
  - Extract local currency when applicable
  - Extract unit of measurement (ones, thousands, millions, billions, or ten_thousands for foreign stocks)
- [x] Validation and error handling (see section 5.5 for two-stage validation details):
  - Stage 1 validation: Verify minimum line count (10 lines) and presence of key totals
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
- [x] Automatic trigger: Income statement processing automatically starts after balance sheet processing completes (for earnings announcements, quarterly filings, and annual reports only)
- [x] Sequential processing: Runs after balance sheet processing to avoid overwhelming Gemini API
- [x] Use balance sheet location to locate income statement:
  - First finds balance sheet location using chunk embeddings
  - Two-stage validation with retry strategy (see section 5.5 for details):
    - Stage 1: Try chunks before, after, and 2 after balance sheet to find correct section (validates line count + required items)
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
  - Extract amortization for the specific time period
  - Extract unit of measurement for each additional item (revenue_prior_year, shares outstanding, amortization)
- [x] Validation and error handling (see section 5.5 for two-stage validation details):
  - Stage 1 validation: Verify minimum line count (5 lines) and presence of required items (Total Net Revenue, Net Income)
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

#### 5.6: Further Updates to Balance Sheet and Income Statement Validation
- [ ] Instead of the complex validation logic after extraction, which wastes output tokens. Ask the LLM do I have a complete consolidated balance sheet starting from cash to total shareholder's equity
- [ ] Simiarly, for the income statement, ask the LLM do I have a complete consolidated income statement starting from revenue to net income. In particular, we need to avoid smaller informational tables that do not have the complete information
- [ ] Keep the old validation logic as a potential future back-up, but do not use it in the main flow for now
- [ ] Similar to how the income statement creates standard names for key line items, the balance sheet should also have standard names for a few key items: cash & equivalents, other current assets, total current assets, other non-current assets, other current liabilities, total current liabilities, other non-current liabilities, total liabilities, total shareholder's equity
- [ ] For balance sheet, income statement, and future additional extractions for additional items, persist the final chunk number used for traceability and observability. The same chunk may also be used repeatedly in the future

### Phase 6: Company Analysis and Adjustments

#### 6.1: Historical Calculations Table for Company View (Complete)
- [x] **Company-Level Historical Calculations Display**
  - Show collected table of historical calculations from all earnings announcements, quarterly filings, and annual reports for the selected company
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
  - Aggregate data from all eligible documents (earnings announcements, quarterly filings, annual reports) for the company

#### 6.2: Major Refactor for placeholders for new Additional Items and Historical Calculations
- [ ] Separate out Additional Items from the income_statement_extractor, validation logic, logging, and progress tracking
- [ ] Create placeholders in the frontend and scaffolds in the backend for additional items: organic growth (prior period revenue and YOY revenue growth should go here), amortization, other assets, other liabilities, total shares outstanding, non-operating assets
- [ ] Keep the current Historical Calculation table as is with two changes: Add Organic Growth to above EBITA and Effective Tax Rate changes to Adjusted Tax Rate. However, this is now the summary table at the end.
- [ ] Create new Historical Calculation section above the summary table with sections called: Invested Capital, Adjusted Tax Rate, EBITA, and NOPAT & ROIC

#### 6.3: Organic Growth
- [ ] Search the document with query: "merge", "acquire", "acquisition", "m&a" and concatenate the top 3 chunks with 0 pages before and after
- [ ] Ask the LLM whether the company made an acquisition within the year and what was the revenue impact on this time period. ZERO toleration for hallucination
- [ ] Show the prior period revenue, the current period revenue, simple revenue growth, the revenue impact from acquisition (show zero if none), current period adjusted revenue, and organic revenue growth (should be same as simple revenue growth if no adjustments)

#### 6.4: Amortization
- [ ] Search the document with query: "amortize", "amortization" and concatenate the top 3 chunks with 0 pages before and after
- [ ] Ask the LLM to identify all the line items for amortization this time period and the value then categorize whether the line item is non-operating (amortization of acquired intangibles, amortization of financing costs) or operating (amortization of capitalized sales costs, amortization of capitalized software). ZERO toleration for hallucination
- [ ] Double check for duplicates and show all the line items with type

#### 6.5: Other Assets
- [ ] Search the document with query: the raw names of the standardized "other current assets", "other non-current assets" (they should have been saved in parentheses) and concatenate the top 3 chunks with 0 pages before and after
- [ ] Ask the LLM to identify all the line items within other current assets and other non-current assets this time period and then categorize whether the line item is non-operating (financial derivatives, currency hedges, investments) or operating. ZERO toleration for hallucination
- [ ] Double check for duplicates and then double check the summation of the line items with the total other current asset and total other non-current assets. If validation fails here, then ask the LLM to double check if the time period is correct
- [ ] Show all the line items with type

#### 6.6: Other Liabilities
- [ ] Search the document with query: the raw names of the standardized "other current liabilities", "other non-current liabilities" (they should have been saved in parentheses) and concatenate the top 3 chunks with 0 pages before and after
- Do similar thing as Other Assets

#### 6.7: Total shares outstanding
- [ ] Search the document with query: "weighted average", "shares", "basic", "diluted" and concatenate the top 3 chunks with 0 pages before and after
- [ ] Ask the LLM to identify the standardized name: basic shares outstanding and diluted shares outstanding
- [ ] Show all the line items

#### 6.8: Non-operating asset
- [ ] Pass the balance sheet line items, other assets (from above), and other liabilities (from above) labeled as non-operating (de-duplicated) to the LLM
- [ ] Ask the LLM to classify each item as: cash (includes items such as restricted cash), short term investments (includes items such as marketable securities), operating lease-related, other financial or physical assets (includes items such as assets held for sale), debt (includes loans, notes), other financial liabilities, deferred tax assets, deferred tax liabilities, preferred equity, minority interest, goodwill/intangibles, UNKNOWN
- [ ] Show all the line items with type

#### 6.9: Invested Capital
- [ ] TBD

#### 6.10: Adjusted Tax Rate
- [ ] TBD

#### 6.11: EBITA
- [ ] TBD

#### 6.12: NOPAT and ROIC
- [ ] TBD

### Phase 7: Financial Modeling
- [ ] TBD

### Phase 8: App-wide Analysis and Dashboard (right panel of the Top-level page)
- [ ] TBD

## Next Steps

- [ ] **Phase 5.4: Adjusted Tax Rate Calculation Fix** (TODO: Needs revisit and fix)
  - Review and fix logic for identifying tax-affecting non-operating items
  - Validate tax shield vs. tax deduction assumptions
  - Improve calculation methodology
  - May need to use LLM to intelligently determine which non-operating items affect taxes
- [ ] **Phase 6.1: Historical Calculations Table for Company View**
  - Company-level historical calculations display
  - Aggregate data from all eligible documents
  - Display in right panel when company is selected
- [ ] **Phase 6.2: Core Analysis Agents**
  - Organic growth assessment agent
  - Operating margin analysis agent
  - Capital turnover evaluation agent
  - Intrinsic value calculation agent (Koller's DCF methodology)
  - Additional items extraction improvements (TODO: needs revisit and fix)
- [ ] **Phase 7: Financial Metrics Display and Analysis**
  - Trend analysis visualization
  - Interactive valuation model UI
  - Sensitivity analysis UI
  - Company analysis results page

## UI/UX Design

For detailed UI/UX specifications and design guidance, see [UI_UX_DESIGN.md](UI_UX_DESIGN.md).

## Clarifications and Notes

### Chunk-Based Document Indexing

**Current Implementation:**
- Documents are split into 2-page chunks for embedding generation during indexing
- Each chunk embedding is persisted to disk (`{document_id}_chunk_{index}_embedding.json`)
- Chunk metadata is stored (`{document_id}_chunks_metadata.json`)
- Extractors reuse persisted chunk embeddings instead of regenerating them
- When extracting sections, extractors search chunks and include 1 page before/after the best match for context
- Eliminates duplicate API calls and improves extraction performance

**Benefits:**
- More granular search: 2-page chunks provide better precision than document-level embeddings while maintaining context
- Performance: Chunk embeddings generated once during indexing, reused during extraction
- Efficiency: No duplicate embedding generation when re-running extractions
- Scalability: Large documents are fully indexed across all chunks

### Financial Statement Processing

**Automatic Processing:**
- Financial statement processing (balance sheet and income statement) is automatically triggered after document indexing completes
- Processing runs sequentially: balance sheet first, then income statement (to avoid overwhelming Gemini API)
- Only eligible document types are processed: earnings announcements, quarterly filings, and annual reports

**Priority-Based Processing Queue:**
- Global priority queue ensures sequential processing to prevent API overload
- Upload step: Parallel (file I/O only, no API calls)
- Classification & Indexing: Sequential via priority queue (priority 0 - highest priority)
- Financial Statement Processing: Sequential via priority queue (priority 1 - lower priority)
- High-priority tasks (classification/indexing) are always processed before lower-priority tasks (financial statements)
- Queue processes: All classification/indexing tasks → All financial statement tasks (if eligible)
- This ensures documents are indexed and searchable before intensive financial statement extraction begins

**Real-Time Progress Tracking:**
- Right panel displays real-time progress tracker when viewing a document
- Milestones tracked:
  - Extracting balance sheet
  - Classifying balance sheet
  - Extracting income statement
  - Extracting additional items (shares outstanding, amortization)
  - Classifying income statement
- Status values: checking (default), pending (processing), in_progress, completed, error, not_found
- Progress updates via polling mechanism (every 3 seconds)
- Progress tracker shows first, financial statements load only when all milestones are terminal
- Database state inference when in-memory progress is unavailable

**Re-run Functionality:**
- Single "Re-run Extraction and Classification" button in document detail view
- Re-runs entire pipeline (balance sheet + income statement)
- Immediately sets all milestones to pending and starts polling
- Button disabled during processing to prevent duplicate runs
- Clears financial statement data before re-running

**Delete Functionality:**
- "Delete Financial Statements" button: Removes all financial statement data for a document
- "Delete Document" button: Permanently deletes document and all associated data (financial statements, embeddings, files)
- Navigates user back to company document list after deletion

**Balance Sheet Validation:**
- Two-stage validation approach (see section 5.5 for complete details)
- Stage 1: Section validation (line count + key lines) with retry across chunk ranks 1, 2, 3
- Stage 2: Calculation validation (sum verification) with LLM feedback retry loop
- Validation logic uses precise regex-based matching to identify totals
- Handles long line item names with notes in parentheses (e.g., "Accounts receivable, net (including consumer financing receivables...)")
- Validation runs in frontend (not persisted) to avoid blocking on validation errors
- Precise total identification using whole-word matching
- Handles descriptive line items with long notes without false positives
- Comprehensive sum verification for assets, liabilities, and equity
- LLM feedback includes calculated differences for better error correction

**Income Statement Validation:**
- Two-stage validation approach (see section 5.5 for complete details)
- Stage 1: Section validation (line count + required items) with retry across chunks before/after/2 after balance sheet
- Stage 2: Post-processing validation (final_diff logic) with LLM feedback retry loop
- Validates gross profit, operating income, and net income calculations during normalization
- Checks for empty line items and key items before validation
- LLM feedback includes calculated differences and cost normalization explanation for better error correction

**API Rate Limiting and Throttling:**
- Centralized Gemini API client with throttling (500ms-2s delays between calls)
- Semaphore-based processing queue:
  - Max 1 concurrent LLM call
  - Max 3 concurrent embedding calls
- Exponential backoff retry logic (2s initial, up to 30s max delay)
- Enhanced rate limit error handling with longer backoff
- Document-level pre-filtering for embedding searches to optimize API calls
- Migration from `google.generativeai` to `google.genai` (new API)

**Balance Sheet Classification:**
- Authoritative lookup table with normalization for binding decisions
- Fallback heuristics when no lookup match
- LLM classification for remaining items
- Normalization: trim, case-insensitive, collapse whitespace, remove leading/trailing punctuation

**Unit Support:**
- Balance sheets and income statements extract and display units (ones, thousands, millions, billions, or ten_thousands)
- Units are extracted by LLM from document notes (e.g., "in millions", "in thousands")
- Units are displayed in financial statement headers (to the right of Currency)
- Additional items each have their own unit field (displayed in Unit column)
- Historical calculations store and display units for monetary values (ratios/percentages show "—")
- Capital Turnover is annualized: For quarterly statements (Q1-Q4), revenue is multiplied by 4 before calculating capital turnover to ensure comparability between quarterly and annual data
- Units are persisted in database and displayed throughout the UI

<!-- Add any clarifications, decisions, or notes here as the project evolves -->
