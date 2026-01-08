# Tiger-Cafe Product Specifications

This document captures the functional requirements, workflows, and architecture for the Tiger-Cafe application.

## Global Dashboard Architecture

### Shared Workspace

All users interact with the same dataset:

- **No user-specific filtering** of companies, documents, or analyses.
- **Attribution is visible** (who uploaded, who initiated analysis).
- **Collaborative workflow** with shared, real-time updates.

### Attribution Display

- User name next to uploaded documents
- User name next to initiated analyses
- Timestamp of actions

## Login Page

### Purpose

The login page is the landing page during development and is the gateway to the shared dashboard.

### User Flow

1. User arrives on login page
2. User clicks **Sign in with Google**
3. OAuth consent screen opens
4. User authorizes access
5. User is redirected back to Tiger-Cafe
6. User lands in the Global Dashboard (two-panel layout)

### UI Requirements

#### Login Card
- Centered card containing a single Google login button
- Minimal distractions (no extra content)

#### Google OAuth Button
- Use Google branding guidelines
- Minimum size: **240px × 40px**
- Blue primary color: **#4285F4**
- Google logo left of text
- Hover: subtle elevation/shadow
- Active: slight press animation

#### Error Handling
- Toast or banner with user-friendly language
- Dismissible errors
- Common errors:
  - OAuth cancellation
  - Network error
  - Server error

#### Loading States
- Centered loading spinner
- “Signing you in…” text
- Prevent multiple clicks while in progress

## Global Dashboard Layout

### Two Adjustable Split Screens

- Vertical split with draggable divider
- Min/max widths: **20% / 80%**
- Default split: **50% / 50%**
- Split preference stored per user

### Left Panel (Navigation)

- Company list (default view)
- **Add Document** button at bottom
  - Changes to **Check Uploads** during active uploads
- Selecting a company shows company documents
- Selecting a document shows document details
  - **Original PDF** viewer (collapsible, default collapsed)
  - Document metadata and status

### Right Panel (Content)

- Default: recent completed analysis list
- Company selected: company analysis dashboard
- Document selected: extracted data + progress view
  - Financial statements tables (Balance Sheet, Income Statement)
  - Historical Calculations (Invested Capital, EBITA, Adjusted Tax, NOPAT, ROIC)
  - Validation indicators
  - Operating vs. non-operating classification
  - Additional items table (Organic Growth, Amortization, Shares)
  - Re-run and delete actions

### Day/Night Toggle

- Location: top-right in header/navbar
- Visual design: icon toggle (sun/moon) or switch
- **Day mode**
  - Background: #FFFFFF / #F5F5F5
  - Text: #212121 / #000000
- **Night mode**
  - Background: #121212 / #1E1E1E
  - Text: #E0E0E0 / #FFFFFF
- Transition: 200–300ms fade
- Preference stored in localStorage

## Phase 2: Document Upload & Classification UI

### Multi-Document Upload Flow

1. User clicks **Add Document**
2. Modal opens with drag-and-drop interface
3. User selects up to 10 PDFs
4. Modal closes immediately after selection
5. Uploads start in parallel (file I/O only)
6. Classification + indexing run sequentially
7. **Add Document** becomes **Check Uploads** with spinner
8. User opens upload progress view
9. Duplicate detection stops at classification with warning
10. If no duplicate, indexing continues automatically
11. After indexing, financial statement processing starts (if eligible)

### Upload Modal Requirements

- Drag-and-drop + manual file picker
- Clear limit indicator: “Upload up to 10 PDF documents”
- Visual drop zone with dashed border
- List of selected files + remove option
- **Upload** button triggers process

### Upload Progress View (Left Panel)

- List of all in-progress documents
- Each item shows:
  - Filename
  - Progress bar with milestones
  - Current status text

### Milestones & Status Indicators

**Milestones**
1. Uploading
2. Classification
3. Indexing

**States**
- Completed: green check
- Active: highlighted with animation
- Pending: muted/gray

### Duplicate Detection UX

- Progress halts at **Classification**
- Warning banner appears
- Shows existing document metadata
- **Replace & Index** button resumes pipeline

### Financial Statement Processing (Document View)

When a document is selected:

- Progress tracker shows **4 milestones**:
  1. Extracting & classifying balance sheet
  2. Extracting & classifying income statement
  3. Extracting additional items
  4. Classifying non-operating items
- Real-time status: `checking`, `pending`, `in_progress`, `completed`, `error`, `not_found`
- Tables include validation status and operating/non-operating labels
- Tables include validation status and operating/non-operating labels

## Historical Metrics & Analysis

The application automatically computes and displays the following based on extracted data:

### 1. Invested Capital
- **Net Working Capital**: Operating Current Assets - Operating Current Liabilities.
  - Breakdowns for components.
- **Net Long-Term Operating Assets**: Operating Non-Current Assets - Operating Non-Current Liabilities.
- **Total Invested Capital**: Sum of the above.

### 2. EBITA & Margins
- **EBITA**: Operating Income adjusted for non-operating items and amortization.
- breakdown of non-GAAP adjustments.

### 3. Adjusted Taxes
- **Adjusted Tax Rate**: Calculated using statutory rate (25%) on deductible adjustments.
- Detailed breakdown of tax effects.
- Comparison with Effective Tax Rate.

### 4. ROI & NOPAT
- **NOPAT**: EBITA * (1 - Adjusted Tax Rate).
- **ROIC**: NOPAT / Invested Capital (Annualized).

### 5. Summary Table
- Aggregates key metrics across all available time periods.
- Includes: Revenue, Growth, EBITA, Margins, Tax Rates, Capital Turnover, ROIC, and Diluted Shares.

## Financial Modeling & Valuation (DCF)

The application provides an interactive Discounted Cash Flow (DCF) model for each company.

### 1. Assumptions Framework
Users can modify key assumptions to drive the valuation model.
- **Organic Revenue Growth**: 3-stage input (Years 1-5, Years 6-10, Terminal Rate).
- **EBITA Margin**: 3-stage input (Years 1-5, Years 6-10, Terminal Rate).
- **Marginal Capital Turnover**: 3-stage input (Years 1-5, Years 6-10, Terminal Rate).
- **Operating Tax Rate**: Single inputs for projected tax rate.
- **WACC**: Weighted Average Cost of Capital (default 8%).
- **Defaults**: System auto-populates defaults based on historical averages (Recent 4 years/quarters).

### 2. Projections Engine (10-Year Forecast)
The model generates a 10-year forecast based on the inputs:
- **Revenue**: Projected using growth rates off the Base Year.
- **EBITA**: Projected using Margin * Revenue.
- **NOPAT**: EBITA * (1 - Tax Rate).
- **Invested Capital**: Projected using the Marginal Capital Turnover ratio (Delta Revenue / MCT).
- **Free Cash Flow (FCF)**: NOPAT - Increase in Invested Capital.

### 3. Terminal Value
Calculated using the **Value Driver Formula** to ensure consistency between growth and ROIC:
- Formula: `Terminal Value = NOPAT_terminal * (1 - g / RONIC) / (WACC - g)`
- **g**: Terminal Growth Rate
- **RONIC**: Return on New Invested Capital (implies marginal efficiency in perpetuity)

### 4. Valuation Output
- **Enterprise Value**: Sum of PV of implicit forecast period FCFs + PV of Terminal Value.
- **Discounting**: Uses **Mid-Year Convention** for cash flows.
- **Intrinsic Value**: Enterprise Value + Non-Operating Assets - Debt (simplified in current phase).
- **Interactive UI**: "Re-run Valuation" button triggers server-side recalculation using preserved assumptions.
