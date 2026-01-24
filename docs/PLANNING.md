# Tiger-Cafe Project Planning

**A private project for Tiger and his friends to play with AI agents performing financial analysis.**

## Project Goals

Build AI agents that can analyze equity investments using principles from Tim Koller's Valuation methodology. The system will provide rigorous financial analysis, intrinsic value calculations, and market sensitivity assessments. This is a personal project for experimentation and learning.

## Technology Stack

- **Language**: Python (FastAPI)
- **Frontend**: React + Vite
- **AI/ML**: Google Gemini (Flash-Lite 2.0 + Embd-001)
- **Database**: SQLite (SQLAlchemy)
- **Auth**: Google OAuth

The system currently supports:
- **Document Management**: Upload, classification, indexing (chunk-based), duplication detection.
- **Financial Extraction**: Balance Sheets, Income Statements, Organic Growth, Amortization, Other Assets/Liabilities, Shares Outstanding.
- **Analysis**: Calculation of Net Working Capital, Invested Capital, EBITA, NOPAT, ROIC, Adjusted Tax Rate.
- **Financial Modeling**: DCF valuation with customizable assumptions, terminal value calculation, intrinsic value estimation.
- **UI**: **View-Based Architecture** using a Dashboard Orchestrator, dedicated Views (`global`, `company`, `document`), and Hook-based logic. Monolithic panels have been removed.

---

## Active Roadmap

## Phases 1-15 Complete
*See `docs/COMPLETED_TASKS.md` for detailed history.*

### Phase 16: Company and Document View feature enhancements
- [x] Refactor Progress Tracking UI/UX
    - [x] Revisit and improve the full list of milestones / logging (See docs/PROGRESS_TRACKING_REFACTOR.md)
    - [x] Remove the processing tracker from the Document Extraction View. Just leave a list of errors/warnings at the top of the page if there are any
    - [x] The Document List View should ONLY pull and show documents that are finished processing
    - Because all processing is now tracked in the check updates page, SSE only needs to work there.
    - Revisit the total number of phases (currently it's 3 in check uploads and 4 in progress tracking)
    - [x] Update the Check Update UI/UX to feel like how modern AI agents are showing how it is thinking (Phase-based milestone view created, SSE integration pending)
- [x] Refactor the routers to be more maintainable. Right now everything is in income_statement.py, which does not make sense. Need to clarify what should be in balance_sheet, income_statement, additional_items, historical_calculations, and documents
- [ ] Improve the Document list
- [ ] Uploading a duplicate document still processed instead of deleting, ending in an error
- [ ] Enable editing extracted values in Document Extraction View
- [ ] In the Document View, add where the Balance Sheet, Income Statement, and Non-GAAP Reconciliation were extracted from
- [ ] Revenue Growth and Margin Sensitivity
- [ ] Fix Time Period to be: Quarter ending in MMM DD, YYYY instead of the ambiguous Q1, Q2, Q3


### Phase 17: Further agent enhancements
- [x] time_period based on quarterly is not reliable. See if can use period_end_date instead. If both are unreliable, then will require some kind of reflection step prior to extraction
- [ ] EL case - LLM extracting after the net earnings / net income line
- [ ] EL case - LLM extracting Non-GAAP table very strangely - look into the non-gaap reconciliation logic
- [ ] EL case - add a reflection step to the Non-GAAP table on time period of line items
- [ ] BIDU case - rare issue where despite using income statement, the prior year revenue is being pulled from a different table (BIDU Core instead of Consolidated)
- [ ] BABA case - the agent is not able to find the balance sheet based on the current chunking and search logic'
- [ ] BABA case - the document does not say which quarter it is only the month, which needs to be interpreted as a certain quarter
- [ ] META case - cannot find shares outstanding for some reason
- [ ] BKNG case - pulled value from a different column despite the reflection step. The LLM struggles with the value is zero, especially if it is represented by "—"
- [ ] TOL case - the balance sheet and income statement does not label important totals for some reason - will need robust reflection step
- [ ] CSCO case - the interest and other expense line is actually a subtotal line. Looking at the csv file, I may have copy & pasted a different company. Need to double check
- [ ] Create a field for document date, which will have many uses. First use is to organize the list of documents (current logic is not great)


### Phase 18: Transcripts, news, and Gemini copy & paste
- [ ] Growth, margin, and capital efficiency assumptions


### Phase 19: 10-K and 10-Q
- [ ] Refactor app to focus on company → period_end_date → documents
- [ ] Enable incorporating multiple document types per period
- [ ] Extract financial statements more consistently
- [ ] Improved organic growth analysis
- [ ] Extract details on amortization, other assets, and other liabilities


## Ongoing List of UI Improvements and Bugs



## Backlog and Notes of Bigger Outstanding Issues - DO NOT CODE
- [ ] Consolidate batch upload tests
- [ ] Refactor opportunity. Send raw pdf using Files API instead of processed text to Gemini
    - Instead of the current chunking logic, use PDF splitters
    - Extract and send global context with prompt
    - Use Gemini 3-flash for the difficult extractions and maintain flash-lite for easier tasks



## Architecture Overview

### Key Implementation Patterns
- **Agent Pattern**: Standalone extractors in `agents/` using `generate_content_safe` (temp=0.0).
- **Document Section Finding**: `find_document_section()` uses embeddings to locate chunks before extraction.
- **Two-Stage Validation**: 
    1. **Completeness Check**: LLM verifies chunk has full table *before* extraction.
    2. **Calculation Validation**: Post-extraction sums check (Assets = Liabilities + Equity, etc.).
- **Standardized Naming**: `Standard Name (Original Name)` format for key line items.
- **Authorization**: Google OAuth with persisted user sessions.
- **Component Architecture**: View-based React components with Hook-based logic (see `docs/ARCHITECTURE.md`).

### Data Flow
1. **Upload** → Classification → Indexing (Sequential queue).
2. **Extraction** (Triggered after indexing):
    - Balance Sheet → Income Statement → Additional Items (Organic Growth, Amortization, etc.).
3. **Calculation**:
    - Historical metrics (ROIC, EBITA, etc.) computed from extracted data.
4. **Modeling**:
    - DCF valuation with customizable assumptions and terminal value calculation.