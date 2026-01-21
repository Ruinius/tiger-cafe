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

## Phases 1-13 Complete
*See `docs/COMPLETED_TASKS.md` for detailed history.*

### Phase 14: Financial Model enhancements
- [x] Create one section with two columns (three fields each) in the Assumptions section between Marginal Capital Turnover and Other
    - The two column section will be called WACC (right now they two sections called Cost of Equity and WACC)
    - One column will have the fields:
        - Beta, pulled, not editable
        - Cost of Equity, calculated, not editable. Use 4.2% for risk free rate. Use 5% for market risk premium.
        - Weight of Equity: pull market cap from Yahoo Finance and divide by that market cap + debt (use the same number as in the Financial model below), calculated, not editable
    - One column will have the fields:
        - Cost of Debt: pull interest expense from the most recent quarter, annualize it, and divide it by debt (use the same number as in the Financial model below). If error, default to using 5%. The number can also not be lower than 5%.
        - Calculated WACC (slight rename), using cost of equity, weight of equity, cost of debt, and 25% Marginal Tax Rate. This is not editable
        - WACC Assumption, default to calculated WACC, but this is the editable field that is used in the rest of the financial model
- [x] Add additional items to the Other column
    - Diluted Shares Outstanding (in the financial model below, the Diluted Shares Outstanding will use this number). Copy the default logic.
    - Base Revenue (in the financial model below, the Revenue line item in Base year will use this number). Copy the default logic.
- [x] Minor edits
    - Change the Marginal Capital Turnover assumption to have two decimals instead of just one
    - Format the Diluted Shares Outstanding field (to be same as in the financial model below)
    - Format the Base Revenue field (to be same as in the financial model below)
- [ ] Add tooltips (little "i" icons I can hover over) for the following fields
    - Cost of Equity
    - Cost of Debt
    - Calculated WACC
- [ ] Add currency translator if currency is not USD
- [ ] Add ADR conversion line if currency is not USD

### Phase 15: App-wide Analysis and Dashboard
- [ ] Improve the Company list
    - Add the date of last valuation with color
- [ ] Analysis Dashboard (Home Page)

### Phase 16: Company View feature enhancements
- [ ] Improve the Document list
- [ ] Revenue Growth and Margin Sensitivity

### Phase 17: Company-Centric Data Model Refactor
- [ ] Refactor app to focus on company → time period → documents
- [ ] Enable incorporating multiple document types per period
- [ ] Historical trend analysis across periods

### Phase 18: Transcripts, news, and analyst reports
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


## Backlog and Notes of Bigger Outstanding Issues - DO NOT CODE
- [ ] EL case - LLM extracting after the net earnings / net income line
- [ ] EL case - LLM extracting Non-GAAP table very strangely - look into the non-gaap reconciliation logic
- [ ] Create a field for document date, which will have many uses. First use is to organize the list of documents (current logic is not great)
- [ ] Fix UI for Uploading flow
    - Milestones in the Progress Tracker are not updating as they should with SSE
    - The UI is not updating as documents flow through the pipeline as they should
    - Allow for continuing to add document and adding them into the pipeline (so the Add document button will never turn into check uploads button)
    - Add a Cell above all the companies that says "Documents Processing" which loads the Check Uploads page
    - Add the Extraction milestones to the Check Uploads page
- [ ] Consolidate batch upload tests
- [ ] Fix the chunk algorithm to be characters based instead of page based search through the first 10 chunks in order of number density
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