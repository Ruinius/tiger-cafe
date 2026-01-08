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

## Future Enhancements - DO NOT CODE
- [ ] **Tagging System**: Replace "Type", "Category", and "Status" columns with a unified **Tagging System**.
  - Single "Tag" column supporting multiple simultaneous tags (e.g., "Operating", "Recurring", "Non-Cash").
  - Status fields becomes a tag (e.g., "Indexed", "Balance Sheet").
- [ ] **UI Interactivity**: Implementation capability to change "Category" and "Type" directly in the UI.
- [ ] Explore using small specialized embedding / encoder models to replace the AUTHORITATIVE_LOOKUP and the classify using LLM

## Current Status (Phases 1-7 Complete)
*See `docs/COMPLETED_TASKS.md` for detailed history.*

The system currently supports:
- **Document Management**: Upload, classification, indexing (chunk-based), duplication detection.
- **Financial Extraction**: Balance Sheets, Income Statements, Organic Growth, Amortization, Other Assets/Liabilities, Shares Outstanding.
- **Analysis**: Calculation of Net Working Capital, Invested Capital, EBITA, NOPAT, ROIC, Adjusted Tax Rate.
- **UI**: Interactive dashboard with document viewer, extraction status, and detailed financial tables.

---

## Active Roadmap

### Phase 8: Financial Modeling
- [x] Fix the company level historical table to give insights
  1. Add the missing fields, so the company level table looks like the one in the document-level Summary Table
  2. Add averages and medians
  3. Add YOY marginal capital turnover

- [x] Add changeable assumptions
  1. Organic revenue growth, allow for first 5 years (default recent average growth), second 5 years (default between first 5 years and terminal), and then terminal growth (default 3%)
  2. EBITA margin, allowing for first 5 years, second 5 years, and then terminal. All defaulting to recent averages
  3. Marginal capital turnover, allowing for first 5 years, second 5 years, and then terminal. All defaulting to average Capital Turnover, Annualized
  4. Adjusted tax rate, single number. Defaulting to recent averages
  5. WACC, single number. Defaulting to 8%

- [x] Add calculations
  1. Revenue, based on growth assumption. Starting value is recent FY or Quarterly annualized.
  2. EBITA and NOPAT, calculated
  3. Invested Capital, calculated using marginal capital turnover. Starting point is average of recent four values
  4. FCF, calculated
  5. Terminal value, calculated using a more robust formula including ROIC
  6. Discount factor with half year adjustment
  7. DCF value, calculated
  10. Non-operating item adjustments (DO NOT CODE)
  11. Fair value per share (DO NOT CODE)
  12. Compare with latest share price, pull from Yahoo Finance API

- [x] Add UI elements on the company-level page

- [ ] Minor UI edits for the right panel in company view - DO NOT CHECK COMPLETE AS I WILL ADD MORE
  1. The top level title should change from "{company} Analysis" to {company} Financial Analysis"
  2. Change "Historical Calculations" to "Historical Data"
  3. Move Currency, Unit, and the short blurb to right under "Historical Data" (should look just like Balance Sheet in the document view)
  4. Remove the title "Financial Modeling"
  5. Move "Assumptions" outside the container to serve as title. Fix the spacing between title and the container (should look just like Balance Sheet in document view)
  6. Add dividers between "Revenue Growth", "EBITA Margin", Marginal Capital Turnover", and "Other" sections
  7. Rename "Revenue Growth" to "Organic Revenue Growth"
  8. Rename "Tax Rate" to "Operating Tax Rate"
  9. Fix the coloring of "Recalculate Model" and rename it to "Re-run Valuation"
  10. Rename "DCF Projections" to "Discounted Cash Flow Model." Fix the spacing between title and the container (should look just like Balance Sheet in document view)
  11. Add a column after column 10 called "Terminal" and fill it with the correct data. The FCF should be Terminal Value and PV of FCF should be PV of Terminal Value
  12. Rename "PV of FCF" to "Present Value"
  13. Rename "Valuation" to "Intrinsic Value" Fix the spacing between title and the container (should look just like Balance Sheet in document view)
  14. In each of the assumption cells, remove the ugly up or down buttons
  15. Fix the number formatting for the numbers in the assumption cells
  16. Remove the code that recalculates every time I change one small assumption and only recalculate when I hit the Re-run button
  17. This may require backend changes as well. The Terminal column should be treated just like any other annual column until the FCF row. Then FCF row should use the above numbers to calculate the Terminal value. Then the discount factor should be filled as well. Then the Present Value uses the Terminal Value and discount factor to calculate. Look at the function formula for how to calculate Terminal value or which discount factor to use.
  18. For the Company Financial Analysis page, for the ROIC value, for frontend purposes, if the number is negative, then just show "negative" if the number is positive but >100%, then just show ">100%"


### Phase 9: App-wide Analysis and Dashboard (right panel of the Top-level page)
- [ ] TBD

### Phase 10: Sensitivity Analysis and Get transcripts, news, and analyst repots to work to provide additional insights.
- [ ] TBD

### Phase 11: Refactor app to focus on company -> time period -> documents, enable incorporating other documents
- [ ] TBD

### Phase 12: Get 10-K and 10-Q to provide additional details.
- [ ] Other assets
- [ ] Other liabilities
- [ ] Organic growth, improved

## Immediate Priorities

*(Add new tasks here)*

## Architecture Overview

### Key Implementation Patterns
- **Agent Pattern**: Standalone extractors in `agents/` using `generate_content_safe` (temp=0.0).
- **Document Section Finding**: `find_document_section()` uses embeddings to locate chunks before extraction.
- **Two-Stage Validation**: 
    1. **Completeness Check**: LLM verifies chunk has full table *before* extraction.
    2. **Calculation Validation**: Post-extraction sums check (Assets = Liabilities + Equity, etc.).
- **Standardized Naming**: `Standard Name (Original Name)` format for key line items.
- **Authorization**: Google OAuth with persisted user sessions.

### Data Flow
1. **Upload** -> Classification -> Indexing (Sequential queue).
2. **Extraction** (Triggered after indexing):
    - Balance Sheet -> Income Statement -> Additional Items (Organic Growth, Amortization, etc.).
3. **Calculation**:
    - Historical metrics (ROIC, EBITA, etc.) computed from extracted data.