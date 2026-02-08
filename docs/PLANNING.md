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

## Phases 1-16 Complete
*See `docs/COMPLETED_TASKS.md` for detailed history.*


### Phase 17: Further agent enhancements
- [x] time_period based on quarterly is not reliable. See if can use period_end_date instead. If both are unreliable, then will require some kind of reflection step prior to extraction
- [x] add a simple LLM-based qualitative economic moat and future growth assessment
    - See detailed plan: @[docs/IMPLEMENTATION_PLAN_QUALITATIVE.md]
- [x] SWK case - the agent cannot find the prior period revenue and current period revenue is screwed up
- [x] CSCO, KO case - the ticker was not identified. Need a reflection step.
- [x] ADP case - organic growth is not working for earnings announcement. For earnings announcement, just do a search for organic growth and see if there's a difference percentage
- [x] APD case - accumulated depreciation is incorrectly shown as a positive number instead of a negative
- [x] Refactor how announcement_date, time_period, and period_end_date are extracted with LLM-driven reflection and self-healing steps across documents
    - EOY / Q4 are the anchors, because there is much less ambiguity
    - There are additional hints in the document, such as "six months", "nine months", "twelve months"
    - There is an opportunity to use the document name (before it is uploaded and the name is lost) as part of the prompt
    - [x] Revisit the reflections for document_classifier, such as comparing period_end_date and time_period, then self-heal time_period before going through the rest of the pipeline
    - [x] Continue to fix time period and period_end_date logic. Some documents have one, some other
    - [x] MA case - the period end date is now missing, and income statement is not being found. This is likely due to time_period being used incorrectly. Need refactor / reflection step for dates and time period
    - [x] ABNB case - dates are mostly missing from the document
    - [x] DIS case - strange case where the extractor fails to find the document date despite it being the first line
    - [x] BABA case - the document does not say which quarter it is only the month, which needs to be interpreted as a certain quarter
    - [x] GIS case - agent is having difficulty with quarters that end on weird months
- [x] BABA case - LLM is confused about using the correct period_end_date and time_period for extracting financial statements
- [x] ABNB case - cannot seem to extract shares outstanding any more
- [x] EL case - cannot seem to extract diluted shares outstanding
- [x] MA case - LLM is not finding the shares outstanding
- [ ] Add reflection and healing step for when key totals are missing, such as total assets, total liabilities, total equity & liabilities
- [ ] EL case - LLM extracting Non-GAAP table very strangely - look into the non-gaap reconciliation logic
- [ ] EL case - add a reflection step to the Non-GAAP table on time period of line items
- [ ] BIDU case - rare issue where despite using income statement, the prior year revenue is being pulled from a different table (BIDU Core instead of Consolidated)
- [ ] BKNG case - pulled value from a different column despite the reflection step. The LLM struggles with the value is zero, especially if it is represented by "—"
- [ ] TOL case - the balance sheet and income statement does not label important totals for some reason - will need robust reflection step
- [ ] DIS case - rare case where total equity & liability is missing
- [ ] DIS case - total PPE line is not labeled and is instead just an indented line
- [ ] WDAY case - there is a strange case where the diluted shares outstanding is not standardized into right units. It looks like the wrong units being extracted for income statement is causing this
- [ ] TTD case - Total other income, net is for some reason not a calculated field
- [ ] NVR case - tiger-transformer does not know how to handle special homebuilding case (WHY ARE ALL THE HOMEBUILDERS SO SPECIAL?!)
- [ ] ULTA case - strange name for net income parent
- [ ] YUMC case - strange name for net income (before parent)
- [ ] WIX case - total revenue line is not labeled
- [ ] CPB case - balance sheet is not being categorized correctly
- [ ] CPB case - for the 10-Q, tiger-transformer does not recognize EBIT


### Phase 18: Research Reports
- [ ] Enable uploading and using Morningstar Research Reports
- [ ] Enable the use of industry Beta (instead of company Beta)


### Phase 19: 10-K and 10-Q
- [x] Make 10-Q go through the same pipeline as earnings announcement for now
- [ ] CPB case - 10-Q somehow got identified as JM Smucker company instead... how?! Try adding a reflection step
- [ ] Need to harmonize when pulling financial statements from the same time period but from 10-Q vs earnings announcement
- [ ] It looks like indexing is not async. Need to make it async
- [ ] Extract financial statements more consistently
- [ ] Improved organic growth analysis
- [ ] Extract details on amortization, other assets, and other liabilities
- [ ] Enable editing extracted values in Document Extraction View
- [ ] GGG case - missing balance sheet in earnings announcement. Need to accelerate analyzing 10-Q and 10-K for complete picture



### Phase 20: Outstanding Refactor Opportunities
- [ ] Refactor all the different status (legacy and new)
- [ ] Refactor opportunity. Send raw pdf using Files API instead of processed text to Gemini
    - Instead of the current chunking logic, use PDF splitters
    - Extract and send global context with prompt
    - Use Gemini 3-flash for the difficult extractions and maintain flash-lite for easier tasks
    - [ ] GRND case - the financial statements are images instead of text
- [ ] Consolidate batch upload tests


## Ongoing List of UI Improvements and Bugs




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