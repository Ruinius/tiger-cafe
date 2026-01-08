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

## Current Status (Phases 1-8 Complete)
*See `docs/COMPLETED_TASKS.md` for detailed history.*

The system currently supports:
- **Document Management**: Upload, classification, indexing (chunk-based), duplication detection.
- **Financial Extraction**: Balance Sheets, Income Statements, Organic Growth, Amortization, Other Assets/Liabilities, Shares Outstanding.
- **Analysis**: Calculation of Net Working Capital, Invested Capital, EBITA, NOPAT, ROIC, Adjusted Tax Rate.
- **Financial Modeling**: DCF valuation with customizable assumptions, terminal value calculation, intrinsic value estimation.
- **UI**: Modular, maintainable React architecture with clean component separation and stable state management.

---

## Active Roadmap

### Phase 9: Financial Modeling (COMPLETE)
Partially completed. See `docs/COMPLETED_TASKS.md` for completed tasks
- [ ] More tasks to be defined

### Phase 10: App-wide Analysis and Dashboard
- [ ] Latest completed analyses on home page
- [ ] Cross-company comparisons
- [ ] Portfolio-level metrics

### Phase 11: Sensitivity Analysis
- [ ] Revenue growth sensitivity
- [ ] Margin sensitivity
- [ ] WACC sensitivity
- [ ] Multi-variable scenario analysis

### Phase 12: Additional Data Sources
- [ ] Integrate transcripts, news, and analyst reports
- [ ] Enhanced 10-K and 10-Q parsing for additional details
- [ ] Improved organic growth analysis

### Phase 13: Company-Centric Refactor
- [ ] Refactor app to focus on company → time period → documents
- [ ] Enable incorporating multiple document types per period
- [ ] Historical trend analysis across periods

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
- **Component Architecture**: Modular React components with Context-based state management (see `docs/REFACTOR_PLAN.md`).

### Data Flow
1. **Upload** → Classification → Indexing (Sequential queue).
2. **Extraction** (Triggered after indexing):
    - Balance Sheet → Income Statement → Additional Items (Organic Growth, Amortization, etc.).
3. **Calculation**:
    - Historical metrics (ROIC, EBITA, etc.) computed from extracted data.
4. **Modeling**:
    - DCF valuation with customizable assumptions and terminal value calculation.