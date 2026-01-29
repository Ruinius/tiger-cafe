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
    - [x] Update the Check Update UI/UX to feel like how modern AI agents are showing how it is thinking (Phase-based milestone view created, SSE integration pending)
- [x] Refactor the routers to be more maintainable. Right now everything is in income_statement.py, which does not make sense. Need to clarify what should be in balance_sheet, income_statement, additional_items, historical_calculations, and documents
- [x] In Check Update, visually, the last document on the bottom is the first one being processed right now. We need to flip this. This should be frontend change ONLY
- [x] A document failed to index properly and now shows up indefinitely in the MissionControlDashboard.
    - Need to double check how can a status update for indexing fail but the rest of the pipeline still runs correctly. I suspect it is because the doc is a duplicate, so the if else checks in indexing is not throwing the correct milestone complete
    - Need code to clean up MissionControlDashboard, effectively failing gracefully
- [x] There is a rare case where the Company Analysis View / Historical Data ends up with "multiple" units
    - Need to leverage the unit changing code (should be in line_item_utils.py) to make sure everything in the Historical Data table is in the predominate unit (e.g, thousands, millions)
    - Refactored companies.py to remove complex calculations into a services layer
- [x] Leverage the unit changing code to make sure that the shares_outstanding in DocumentExtractionView is in the same units, showing three decimal places, as the income_statement. This will likely require a backend change as well that saves the new value and new units
- [x] DocumentExtractionView is incorrectly showing Organic Growth table with currency = N/A, and unit is missing. We should take and show the currency and unit from the current_revenue that is being passed from income_statement
- [x] Create a field for document_date, which will have many uses.
    - document_classifier will extract this date in addition to time_period and period_end_date in the same prompt. However, it needs to be clear that document_date and period_end_date are different dates
    - In DocumentView, show document date after Type and before Time Period. Ensure that it is formatted correctly using the global formatter
    - In Company List, replace period_end_date with document_date. Rename "Date Financial Cover" to "Most Recent Document"
    - In Company List, replace "Date Financials Cover" to "Most Recent Document" in the sort
- [x] SSE should only drive re-render on the MissionControl, but I am getting re-render in all pages, which makes editing impossible
- [x] The system correctly detects duplicate and stops the pipeline, but the document still sits in the processing pipeline in MissionControl indefinitely
- [x] Fix ghost companies (0 documents) reappearing in company list when sorting
- [x] In the DocumentExtractionView, for each of the tables (e.g., Balance Sheet) to the right of "Unit", add and populate "Chunk Index:" as appropriate
- [x] Change the @financialmodel.jsx such that the revenue growth transition is smooth. So Stage 1 (Y1-5) is really just defining Y1. Stage 2 (Y6-10) is only defining Y6. Then the in between years are straight-line smoothed out
- [x] Change raw beta in @financialmodel.jsx to use Blume's adjustment (basically 2/3 raw beta and 1/3 = 1.0). Change the label from "Beta" to "Adjusted Beta" and add a tooltip explaining the adjustment
- [ ] Improve the Document list
- [ ] Enable editing extracted values in Document Extraction View
- [ ] Revenue Growth and Margin Sensitivity


### Phase 17: Further agent enhancements
- [x] time_period based on quarterly is not reliable. See if can use period_end_date instead. If both are unreliable, then will require some kind of reflection step prior to extraction
- [x] add a simple LLM-based qualitative economic moat and future growth assessment
    - See detailed plan: @[docs/IMPLEMENTATION_PLAN_QUALITATIVE.md]
- [ ] add a reflection step for the meta data of all the documents, such as comparing period_end_date and time_period, then self-heal time_period before going through the rest of the pipeline
- [ ] Continue to fix time period and period_end_date logic. Some documents have one, some other.
- [ ] EL case - LLM extracting after the net earnings / net income line
- [ ] EL case - LLM extracting Non-GAAP table very strangely - look into the non-gaap reconciliation logic
- [ ] EL case - add a reflection step to the Non-GAAP table on time period of line items
- [ ] EL case - cannot seem to extract dilted shares outstanding
- [ ] BIDU case - rare issue where despite using income statement, the prior year revenue is being pulled from a different table (BIDU Core instead of Consolidated)
- [ ] BABA case - the agent is not able to find the balance sheet based on the current chunking and search logic'
- [ ] BABA case - the document does not say which quarter it is only the month, which needs to be interpreted as a certain quarter
- [ ] META case - cannot find shares outstanding for some reason
- [ ] BKNG case - pulled value from a different column despite the reflection step. The LLM struggles with the value is zero, especially if it is represented by "—"
- [ ] TOL case - the balance sheet and income statement does not label important totals for some reason - will need robust reflection step
- [ ] CSCO case - the interest and other expense line is actually a subtotal line. Looking at the csv file, I may have copy & pasted a different company. Need to double check
- [x] SWK case - the agent cannot find the prior period revenue and current period revenue is screwed up
- [x] CSCO, KO case - the ticker was not identified. Need a reflection step.
- [ ] JD case - need to fix the labeling for equity method, because they need to be treated differently for adjusted tax calculations
- [ ] DIS case - rare case where total equity & liability is missing
- [ ] DIS case - total PPE line is not labeled and is instead just an indented line
- [ ] ABNB case - dates are mostly missing from the document
- [ ] TXN case - PPE total is not marked correctly, causing validation to fail and invested capital to be exaggerated
- [ ] MTCH case - there's a strange situation where total other income, net is not a calculated field
- [ ] WDAY case - there is a strange case where the diluted shares outstanding is not standardized into right units
- [ ] RKT case - tiger-transformer does not know how to handle mortgage company


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
- [ ] Refactor all the different status (legacy and new)
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