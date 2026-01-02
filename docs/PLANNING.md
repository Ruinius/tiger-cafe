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
7. User can view progress by clicking "Check Uploads" button (shows upload progress view with milestones)
8. System automatically navigates back to companies list when uploads complete

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
     - Financial analysis processing status
5. User can trigger financial analysis on unprocessed documents ONLY

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
- [x] Trigger balance sheet processing for earnings announcements, quarterly filings, and annual reports only
- [x] Use document embedding to locate the consolidated balance sheet section
- [x] LLM-based extraction of balance sheet line items:
  - Extract balance sheet exactly line by line for the specified time period
  - Extract local currency when applicable
- [x] Validation and error handling:
  - Verify that current assets sum correctly
  - Verify that total assets sum correctly
  - Verify that current liabilities sum correctly
  - Verify that total liabilities sum correctly
  - Verify that total assets equal total liabilities and total equity
  - If sums are incorrect, retry extraction up to 3 times before failing
- [x] Line item classification:
  - Use LLM to categorize each balance sheet line item as operating or non-operating
  - Use "balance_sheet_items.csv" as additional context, but LLM should use best judgment
- [x] Data persistence and display:
  - Persist balance sheet extraction and line item classification
  - Display balance sheet data in right panel when document is selected in left panel

#### 5.2: Income Statement Processing
- [ ] Use document embedding to locate the income statement:
  - May be called by various names (e.g., "consolidated statement of operations")
  - Use embedding-based search to find the relevant section
- [ ] LLM-based extraction of income statement line items:
  - Extract income statement exactly line by line for the specified time period
  - Extract local currency when applicable
  - Extract revenue for the same period in the prior year (for year-over-year growth calculation)
- [ ] Additional data extraction (using embedding and LLM):
  - Extract total shares outstanding for the specific time period
  - Extract diluted shares outstanding for the specific time period
  - Extract amortization for the specific time period
- [ ] Validation and error handling:
  - Verify gross profit calculation
  - Verify operating income calculation
  - Verify net income calculation
  - If sums are incorrect or errors occur, retry extraction up to 3 times before failing
- [ ] Line item classification:
  - Use LLM to categorize each income statement line item as operating or non-operating
  - LLM should use best judgment for classification
- [ ] Data persistence and display:
  - Persist income statement extraction
  - Persist line item classification
  - Persist revenue growth calculation (year-over-year)
  - Persist shares outstanding (total and diluted)
  - Persist amortization
  - Display all income statement data in right panel when document is selected in left panel

#### 5.3: Historical Calculations
- [ ] (Placeholder for historical calculations requirements)

### Phase 6: Core Analysis Agents
- [ ] Organic growth assessment agent
- [ ] Operating margin analysis agent
- [ ] Capital turnover evaluation agent
- [ ] Intrinsic value calculation agent (Koller's DCF methodology)
- [ ] Market belief analysis agent
- [ ] Sensitivity analysis agent

### Phase 7: Financial Metrics Display and Analysis (Epic 3)
- [ ] Financial metrics persistence
- [ ] Trend analysis visualization
- [ ] Interactive valuation model UI
- [ ] Sensitivity analysis UI with adjustable assumptions
- [ ] LLM-driven summary generation from analyst reports
- [ ] Company analysis results page

### Phase 8: Integration and Enhancement
- [ ] Agent coordination and workflow management
- [ ] End-to-end analysis pipeline
- [ ] Online search integration for growth/margin/turnover insights (future)
- [ ] Error handling and validation
- [ ] Performance optimization
- [ ] Documentation and testing improvements

## Next Steps

1. Complete Phase 3.3 enhancements:
   - Document count badges on company list
   - Breadcrumb navigation
   - Attribution display (uploader name)
2. Complete Phase 3.4 enhancements:
   - Implement actual data display for latest completed analyses
   - Summary cards for company analyses
3. Phase 4 remaining items:
   - Trigger financial analysis functionality
4. Phase 5: Financial Statement Processing
5. Phase 6: Core Analysis Agents

## UI/UX Design

For detailed UI/UX specifications and design guidance, see [UI_UX_DESIGN.md](UI_UX_DESIGN.md).

## Clarifications and Notes

### Document Size Limitations (Future Enhancement)

**Current Limitation:**
- The document indexer currently truncates text to 20,000 characters for embedding generation
- Only the first ~20,000 characters of large documents (e.g., 500-page annual reports) are searchable
- PDF extraction can handle unlimited pages, but processing may be slow for very large documents

**Future Enhancement:**
- Implement chunk-based indexing for large documents (split into multiple embeddings)
- Increase embedding character limit if Gemini API allows
- Add page-based extraction limits to prevent memory issues
- Consider implementing document summarization for sections beyond the indexed portion

<!-- Add any clarifications, decisions, or notes here as the project evolves -->

