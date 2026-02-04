# Completed Tasks

This document serves as an archive of completed tasks from the Project Planning.

## Phase 1: Foundation and Authentication
- [x] Project setup, Git init, Gemin API setup
- [x] Authentication (Google OAuth) & Database schema (SQLAlchemy/Pydantic)
- [x] Basic web framework (FastAPI) & Data structures

## Phase 2: Document Upload and Classification
- [x] PDF upload & Text extraction
- [x] Document classification & Indexing (LLM-based)
- [x] Duplicate detection & Metadata storage
- [x] Priority-based processing queue

## Phase 3: Frontend UI - Global Dashboard
- [x] Login Page & Global Dashboard Layout
- [x] Left/Right Panel Split & Navigation
- [x] Document Upload Flow with Progress Tracking

## Phase 4: Company and Document Management (Backend)
- [x] Listing APIs & Status tracking
- [x] Real-time updates (Polling initially)
- [x] Document Type-Based Processing Status

## Phase 5: Financial Statement Processing
- [x] **Balance Sheet**: Sequential trigger, Chunk search, Extraction, Validation
- [x] **Income Statement**: Sequential trigger, Proximity search, Extraction, GAAP/EBITDA Recon
- [x] **Historical Calculations**: NWC, Invested Capital, EBITA, Tax Rate
- [x] **Enhanced Validations**: LLM-Enhanced identification (Operating/Non-Operating), Completeness checks

## Phase 6: Company Analysis and Adjustments
- [x] Historical Calculations Table
- [x] Additional Items Extraction: Organic Growth, Amortization, Other Assets/Liabilities, Shares Outstanding
- [x] Non-Operating Asset Classification
- [x] Metric Refinements: Invested Capital, Adjusted Tax Rate, EBITA, NOPAT, ROIC

## Phase 7: UI Standardization and Refinement
- [x] Button Logic & UI Standardization
- [x] Historical Calculations Table Polish
- [x] Robust Extraction & Validation (Multi-stage)

## Phase 8: Frontend Refactor & Code Organization
- [x] Component Split (Left/Right Panel -> separate components)
- [x] Logic Extraction (Custom hooks)
- [x] Directory Restructuring (`views/`, `common/`)

## Phase 9: Financial Modeling (DCF Valuation)
- [x] Historical Data Enhancements (Yields, Averages)
- [x] DCF Assumptions Framework & Calculations (FCF, Terminal Value, Intrinsic Value)
- [x] UI Implementation (Projections, Intrinsic Value Bridge)

## Phase 10: View-Based Frontend Architecture Refactor
- [x] **Architecture**: Moved to `views/` structure, eliminated monolith panels
- [x] **Orchestration**: `Dashboard.jsx` manages View State
- [x] **Stand-alone Views**: Welcome, CompanyList, DocumentList, etc.

## Phase 11: User Authentication & Security
- [x] JWT Implementation & Password Hashing (BCrypt)
- [x] Login Flow (Email/Password) & Persistent Sessions

## Phase 12: Stream & Stability Improvements
- [x] **SSE Integration**: Server-Sent Events for status updates
- [x] E2E Reliability & React Fixes

## Phase 13: Tiger-Transformer Integration & Pipeline Refactor
- [x] **Integration**: Created `TigerTransformerClient` for local inference
- [x] **Pipeline**: Integrated Transformer into BS/IS line item processing (Classification, Standardization)
- [x] **Frontend Fixes**: Non-GAAP Recon, Non-Operating Classification, Invested Capital tables logic

## Phase 14: Financial Model Enhancements
- [x] **WACC**: Two-column inputs, Cost of Equity/Debt calculations
- [x] **New Assumptions**: Diluted Shares, Base Revenue defaults
- [x] **Currency/ADR**: Exchange rates (Yahoo Finance), ADR conversion support

## Phase 15: App-wide Analysis and Dashboard
- [x] **Company List**: Card view with Valuation Status, Sorting
- [x] **Analysis Dashboard**: Global visualizations (Valuation History, Rule of 40)

## Phase 16: Company and Document View Feature Enhancements
- [x] **Progress Tracking Refactor**: 
    - Implemented phase-based progress tracking (12 steps)
    - Removed embedded tracker from Extraction View (replaced with error banners)
    - Updated Check Updates UI/UX
- [x] **Router Refactor**: Organized routers by domain (balance_sheet, income_statement, etc.)
- [x] **UI/UX Improvements**:
    - "Check Update" list order flipped (newest top)
    - Cleaned up duplicate document handling in dashboard
    - Fixed infinite re-renders on SSE updates
- [x] **Data Consistency**:
    - **Unit Normalization**: Ensured Historical Data and Shares Outstanding use predominant units (millions/thousands)
    - **Currency/Unit Persistence**: Fixed Organic Growth table missing units
    - **Document Date**: Added explicit `document_date` field (distinct from period end), updated sorting/display
- [x] **Financial Model Polish**:
    - **Smoothing**: Revenue growth and EBITA margin transitions
    - **Adjusted Beta**: Implemented Blume's adjustment
    - **Formatting**: Fixed currency/number formatting in Past Valuations and Share Price
- [x] **Document List & Badges**:
    - Added "Time Period" column
    - Added Status Badges: **BS** (Balance Sheet), **IS** (Income Statement), **OG** (Organic Growth), **SO** (Shares Outstanding), **dup** (Duplicate)
    - Implemented badge tooltips and color coding (Green/Yellow/Red)