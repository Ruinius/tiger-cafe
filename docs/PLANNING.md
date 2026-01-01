# Tiger-Cafe Project Planning

## Project Goals

Build AI agents that can analyze equity investments using principles from Tim Koller's Valuation methodology. The system will provide rigorous financial analysis, intrinsic value calculations, and market sensitivity assessments.

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

### Epic 1: Document Upload and Classification

**User Flow:**
1. User logs in using Google account (OAuth)
2. User uploads a PDF document
3. System reads first few pages of PDF
4. LLM determines:
   - Document type (earnings announcement, quarterly filing, annual filing, other press release, analyst report, news article)
   - Time period
   - Company identification
5. For earnings announcements, quarterly filings, and annual reports:
   - Check if document is duplicative
   - If duplicative: inform user and offer navigation to company page
   - If new: ask for confirmation before indexing
6. Index document using Google's embedding model (gemini-embedding-001)
7. Navigate to company page

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
- **Web Framework**: [To be determined - FastAPI/Flask/Django?]
- **Frontend**: [To be determined - React/Vue/vanilla JS?]
- **Authentication**: Google OAuth
- **Document Processing**: PDF parsing libraries (PyPDF2, pdfplumber, etc.)
- **Data Processing**: Pandas, NumPy, yfinance
- **Database**: [To be determined - PostgreSQL/SQLite/MongoDB?]
- **Storage**: Local cache + database for persistence
- **Configuration**: python-dotenv for API key management

## Development Phases

### Phase 1: Foundation and Authentication (Current)
- [x] Project setup and structure
- [x] Git repository initialization
- [x] Basic configuration system (Gemini API setup)
- [ ] Authentication system (Google OAuth)
- [ ] Database schema design
- [ ] Basic web framework setup
- [ ] Data structure definitions

### Phase 2: Document Upload and Classification (Epic 1)
- [ ] PDF upload functionality
- [ ] PDF text extraction (first few pages)
- [ ] Document classification agent (LLM-based)
  - Document type detection
  - Time period extraction
  - Company identification
- [ ] Duplicate detection system
- [ ] Document indexing with Gemini embeddings
- [ ] Document metadata storage
- [ ] User confirmation workflow

### Phase 3: Company and Document Management (Epic 2)
- [ ] Company listing page
- [ ] Company document listing page
- [ ] Document status tracking (indexing, processing)
- [ ] Progress indicators for indexing/processing
- [ ] Trigger financial analysis functionality
- [ ] Document summary persistence

### Phase 4: Financial Statement Processing
- [ ] Financial statement parser agent
- [ ] Financial statement adjustment agent (Koller's principles)
- [ ] Data normalization and structuring
- [ ] Testing with sample financial data

### Phase 5: Core Analysis Agents
- [ ] Organic growth assessment agent
- [ ] Operating margin analysis agent
- [ ] Capital turnover evaluation agent
- [ ] Intrinsic value calculation agent (Koller's DCF methodology)
- [ ] Market belief analysis agent
- [ ] Sensitivity analysis agent

### Phase 6: Financial Metrics Display and Analysis (Epic 3)
- [ ] Financial metrics persistence
- [ ] Trend analysis visualization
- [ ] Interactive valuation model UI
- [ ] Sensitivity analysis UI with adjustable assumptions
- [ ] LLM-driven summary generation from analyst reports
- [ ] Company analysis results page

### Phase 7: Integration and Enhancement
- [ ] Agent coordination and workflow management
- [ ] End-to-end analysis pipeline
- [ ] Online search integration for growth/margin/turnover insights (future)
- [ ] Error handling and validation
- [ ] Performance optimization
- [ ] Documentation and testing improvements

## Next Steps

1. Set up GitHub repository (git needs to be installed/configured)
2. Determine web framework and frontend stack
3. Design database schema for companies, documents, and analysis results
4. Implement Google OAuth authentication
5. Build document upload and PDF processing pipeline
6. Develop document classification agent

## Clarifications and Notes

<!-- Add any clarifications, decisions, or notes here as the project evolves -->

