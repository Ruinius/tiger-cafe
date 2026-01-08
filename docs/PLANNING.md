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
- [ ] TBD

### Phase 9: App-wide Analysis and Dashboard (right panel of the Top-level page)
- [ ] TBD

### Phase 10: Refactor app to focus on company -> time period -> documents, enable incorporating other documents
- [ ] TBD

### Phase 11: Get transcripts, news, and analyst repots to work to provide additional insights.
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