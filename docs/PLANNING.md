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

## Phases 1-14 Complete
*See `docs/COMPLETED_TASKS.md` for detailed history.*

### Phase 15: App-wide Analysis and Dashboard
- [x] Improve the Company list
    - Transformed list to card view displaying Valuation Status, Last Doc Date, and % Undervalued (Color Coded)  
    - Added sorting controls (Name, Last Doc, Valuation, Status) and standardized date formats
    - Updated default panel split to 50/50 and removed legacy badges
    - [x] Change the card labels
        1. Last Doc -> Date Financials Cover
        2. Valuation -> Most Recent Valuation
        3. Status -> Over/under-valuation

- [x] Analysis Dashboard (Home Page)
    - Implemented global visualizations defined in `docs/DASHBOARD_IDEAS.md`
    - Added Valuation History scatter plot and Rule of 40 (Margin vs Growth) chart with L4Q logic

### Phase 16: Company View feature enhancements
- [ ] Improve the Document list
- [ ] Revenue Growth and Margin Sensitivity

### Phase 17: Company-Centric Data Model Refactor
- [ ] Refactor app to focus on company → time period → documents
- [ ] Enable incorporating multiple document types per period
- [ ] Historical trend analysis across periods

### Phase 18: Transcripts, news, and Gemini copy & paste
- [ ] Growth, margin, and capital efficiency assumptions

### Phase 19: 10-K and 10-Q
- [ ] Improve the chunk query logic. For example, filter for top 10 number dense chunks, then check for similarity
- [ ] Extract financial statements more consistently
- [ ] Improved organic growth analysis
- [ ] Extract details on other assets and other liabilities

## Ongoing List of UI Improvements and Bugs
- [x] For financial statement extraction, the chunks need to have a critical mass of numbers (at least 15 for balance sheet and income statement. At least 10 for Non-GAAP Reconciliation) to be included in the list of chunks considered
- [x] Fix the LLM prompts checking for completion e.g., Q1 Fiscal 2026 or Q1 FY26
- [x] For finding the balance sheet, if the best rank chunk is the first or last chunk, push its rank down by two (given there are three tries, it will still be tried but last)
- [x] BIDU case - screwed up numbers in PDF and Validation failed: unsupported operand type(s) for +: 'int' and 'NoneType'
- [x] Fix Time Period identification. LLM is not following the format restriction
- [x] Improve the prompt to find complete financial statement, especially when fiscal year and calendar year are not the same
- [x] When uploading document, I get this error - Could not get FontBBox from font descriptor because None cannot be parsed as 4 floats at the beginning, especially during indexing
- [x] Improve find_document_section
    - Keep the old function as _legacy with comment to not delete it (in case we need to revert)
    - Rank each chunk by number density and have the app run through the five most number dense chunks plus their previous and next one page
    - So balance sheet will run through up to five chunks until LLM validation finds the complete balance sheet
    - Income statement will run through up to five chunks until LLM validation finds the complete income statement
    - Non-GAAP validation will run through up to five chunks until LLM validation finds the relevant table
- [x] Pulled revenue growth extraction and calculation out of the main income statement extraction for better consistency
- [x] BIDU case - Adjusted Tax Rate is using pretax income as a line
- [x] Fix the chunk algorithm to be characters based instead of page based search through the first 10 chunks in order of number density
    1. Change from 2 pages per chunk to 5000 characters per chunk
    2. Replace any page_after or page_before from 1 pages to 2500 characters
    3. Change the algorithm for finding the balance sheet and income statement to first filter the chunks for top-10 based on number density
    4. Then rank the top-10 chunks based on the query (these should still be saved somewhere in the extractor agents)
    5. Double check all the different extractors to ensure the refactor works


## Backlog and Notes of Bigger Outstanding Issues - DO NOT CODE
- [ ] EL case - LLM extracting after the net earnings / net income line
- [ ] EL case - LLM extracting Non-GAAP table very strangely - look into the non-gaap reconciliation logic
- [ ] EL case - add a reflection step to the Non-GAAP table on time period of line items
- [ ] BIDU case - rare issue where despite using income statement, the prior year revenue is being pulled from a different table (BIDU Core instead of Consolidated)
- [ ] BABA case - uploading a duplicate document still processed instead of deleting, ending in an error
- [ ] BABA case - the agent is not able to find the balance sheet based on the current chunking and search logic
- [ ] META case - cannot find shares outstanding for some reason
- [ ] Create a field for document date, which will have many uses. First use is to organize the list of documents (current logic is not great)
- [ ] Fix UI for Uploading flow
    - Milestones in the Progress Tracker are not updating as they should with SSE
    - The UI is not updating as documents flow through the pipeline as they should
    - Allow for continuing to add document and adding them into the pipeline (so the Add document button will never turn into check uploads button)
    - Add a Cell above all the companies that says "Documents Processing" which loads the Check Uploads page
    - Add the Extraction milestones to the Check Uploads page
- [ ] Consolidate batch upload tests
- [ ] Improve the order in which content is loaded in Document Extraction View for better UX
- [ ] Improve the order in which content is loaded in Company Analysis View for better UX
- [ ] Enable editing extracted values in Document Extraction View
- [ ] In the Document View, add where the Balance Sheet, Income Statement, and Non-GAAP Reconciliation were extracted from
- [ ] Add additional log for Stage 2 Validation for all extractions (e.g., what's the LLM's response on time period alignment)
- [ ] Review the full logging and fix legacy inaccuracies such as income statement finishing very late in logs
- [ ] Failing to find the Non-GAAP Reconciliation (or any items under additional items) should just be a warning instead of an error


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