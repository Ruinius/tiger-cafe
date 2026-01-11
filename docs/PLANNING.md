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

## Current Status (Phases 1-10 Complete)
*See `docs/COMPLETED_TASKS.md` for detailed history.*

The system currently supports:
- **Document Management**: Upload, classification, indexing (chunk-based), duplication detection.
- **Financial Extraction**: Balance Sheets, Income Statements, Organic Growth, Amortization, Other Assets/Liabilities, Shares Outstanding.
- **Analysis**: Calculation of Net Working Capital, Invested Capital, EBITA, NOPAT, ROIC, Adjusted Tax Rate.
- **Financial Modeling**: DCF valuation with customizable assumptions, terminal value calculation, intrinsic value estimation.
- **UI**: **View-Based Architecture** using a Dashboard Orchestrator, dedicated Views (`global`, `company`, `document`), and Hook-based logic. Monolithic panels have been removed.

---

## Active Roadmap

### Phase 10: View-Based Frontend Architecture (COMPLETE)
See `docs/COMPLETED_TASKS.md` for details.
- [x] Structural Reorganization (`views/`, `layout/`, `modals/`)
- [x] Logic Extraction (Custom Hooks)
- [x] Dashboard Orchestration
- [x] Removal of Monoliths (`LeftPanel`, `RightPanel`)

### Phase 11: Financial Model enhancements
- [ ] CAPM for WACC in a separate column
    - risk-free rate and global assumption
    - expected market return and global assumption
    - beta for company (Yahoo Finance?)
- [ ] New Assumption Fields in the Other column
    - Diluted Shares Outstanding
    - Base Revenue

### Phase 12: App-wide Analysis and Dashboard
- [ ] Improve the Company list
    - Remove the # of documents badge
    - Add the date of last valuation with color
- [ ] Analysis Dashboard (Home Page)

### Phase 13: Company View feature enhancements
- [ ] Improve the Document list
- [ ] Revenue Growth and Margin Sensitivity

### Phase 14: Company-Centric Data Model Refactor
- [ ] Refactor app to focus on company → time period → documents
- [ ] Enable incorporating multiple document types per period
- [ ] Historical trend analysis across periods

### Phase 15: Transcripts, news, and analyst repots
- [ ] Growth, margin, and capital efficiency assumptions

### Phase 16: 10-K and 10-Q
- [ ] Improved organic growth analysis
- [ ] Extract details on other assets and other liabilities

## Ongoing List of UI Improvements and Bugs
- [ ] Improve page loading speed and/or content order
- [ ] Tool tips for key formulas and assumptions
- [ ] Enable editing extracted values in Document Extraction View
- [ ] Fix UI and frontend for Uploading flow
- [ ] Fix Time Period identification. LLM is not following the format restriction
- [ ] Failing to find the Non-GAAP Reconciliation should just be a warning instead of an error
- [ ] For financial statement extraction, the chunks need to have a critical mass of numbers (at least 15 for balance sheet and income statement. At least 10 for Non-GAAP Reconciliation) to be included in the list of chunks considered
- [ ] For finding the balance sheet, if the best rank chunk is the first or last chunk, push its rank down by two (given three tries, it will still be tried but last)


## Backlog and Notes of Bigger Outstanding Issues
- [ ] BIDU case - screwed up numbers in PDF and Validation failed: unsupported operand type(s) for +: 'int' and 'NoneType'
- [ ] INTU case - edge case balance sheet
- [ ] TGT case - edge case balance sheet
- [ ] EL case - interest income and interest expense lines are both positive!
- [ ] Create an extraction field for document date, which will have many uses. First use is to organize the list of documents (current logic is not great)
- [ ] Create a custom tiny transformer to rename line items and manage classification
- [ ] Use the results from the tiny transformer to handle bolding logic (current logic is not great)


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

