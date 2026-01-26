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

## Frontend Architecture

### Overview

The frontend implements a **view-based state machine** where the application state is defined by the user's depth of navigation. Instead of fixed "Left/Right" panel components, the app renders distinct **Views** that define the content of both panels simultaneously.

The `Dashboard.jsx` component acts as the central orchestrator, managing three distinct states and their corresponding view compositions.

### State Machine

The application operates in one of three states at any given time:

```
GLOBAL → COMPANY → DOCUMENT
  ↑         ↑
  └─────────┘
```

Navigation is hierarchical:
- Users start at **GLOBAL** (company list)
- Selecting a company transitions to **COMPANY** (document list + company analysis)
- Selecting a document transitions to **DOCUMENT** (document details + extraction view)
- Breadcrumb navigation allows returning to previous states

### State 1: Global Dashboard (Home)

**Trigger**: Initial Load / "Companies" Breadcrumb

**Left Panel**: `CompanyList`
- **Card-Based View**: Displays companies as cards with:
  - Name and Ticker
  - **Date Financials Cover**: The specific period of the latest data.
  - **Most Recent Valuation**: Fair Value and Date.
  - **Over/Under-valuation**: Color-coded status (Green/Red).
- Searchable list of all companies
- "Add Document" entry point
- "Check Uploads" entry point (when uploads are active)

**Right Panel**: `WelcomeView` (Global Analysis Dashboard)
- **Valuation History**: Scatter plot showing Over/Under-valuation trends over time across the portfolio.
- **Rule of 40 Map**: Scatter plot comparing Revenue Growth vs EBITA Margin to identify high-performance companies.
- Global recent activity
- System-wide stats

**CSS**: `Dashboard.css`

### State 2: Company Overview

**Trigger**: User selects a Company

**Left Panel**: `DocumentList`
- Breadcrumb: `< Companies`
- List of documents belonging to the selected company
- "Add Document" entry point (pre-selects company)
- "Check Uploads" entry point (when uploads are active)

**Right Panel**: `CompanyAnalysisView`
- Aggregated metrics for the company
- Financial Model / Valuation summary (DCF)
- Cross-document trends

**CSS**: `Company.css`

### State 3: Document Analysis

**Trigger**: User selects a Document

**Left Panel**: `DocumentView`
- Breadcrumb: `< [Company Name]`
- Collapsible PDF viewer (default collapsed)
- Document Metadata (Status, Type, Upload Attribution)

**Right Panel**: `DocumentExtractionView`
- Tabbed interface for Extractions (Balance Sheet, Income Statement) vs Analysis (Calculations)
- Specific validation controls for the active document
- Re-run and delete actions

**CSS**: `Document.css`

### Global Interactions (Modals)

Modals are rendered at the `Dashboard` level and are accessible across all three states:

#### Upload Modal
- **Trigger**: "Add Document" button (available in Company List & Document List)
- **Behavior**: Modal dialog for file selection (drag-and-drop + file picker)
- **Context-Aware**: Pre-selects company if triggered from Company or Document view

#### Mission Control Modal
- **Trigger**: "Check Uploads" button (replaces "Add Document" when uploads are active)
- **Behavior**: A high-fidelity "Command Center" dialog showing the real-time "Intelligence Stream" of all document processing missions.
- **The Intelligence Stream**:
  - **Real-time Logs**: Granular events that "drip" in as they happen.
  - **Source Differentiation**: Visually identifies where info comes from:
    - `SYSTEM`: Internal orchestration steps.
    - `GEMINI`: AI reasoning, extraction, and validation responses.
    - `TIGER TRANSFORMER`: Technical standardization and P&L mapping.
  - **Milestones**: Status indicators (Uploading → Classification → Indexing → Extraction).
  - **Features**:
    - Duplicate detection warnings with "Replace & Index" actions.
    - Direct "Gemini response" snippets providing transparency into AI logic.

### Context Providers

The application uses React Context for global state management:

#### AuthContext
- Provides authentication state (`isAuthenticated`, `user`, `token`)
- Handles login/logout flows
- Manages token verification and refresh
- Intercepts 401 responses to handle session expiration

#### ThemeContext
- Provides theme state (`light` / `dark`)
- Persists theme preference to localStorage
- Applies theme to document root via `data-theme` attribute

#### UploadContext
- Manages upload state tracking
- Listens to Server-Sent Events (SSE) via `useStatusStream.js` for real-time updates
- Provides `uploadingDocuments` array and `showUploadProgress` flag
- Automatically handles reconnection and session expiration

### Component Hierarchy

```
App.jsx
├── ThemeProvider
│   ├── AuthProvider
│   │   ├── UploadProvider
│   │   │   ├── Router
│   │   │   │   ├── LoginPage (unauthenticated)
│   │   │   │   └── Dashboard (authenticated)
│   │   │   │       ├── Header
│   │   │   │       ├── SplitScreen
│   │   │   │       │   ├── [Left Panel View]
│   │   │   │       │   └── [Right Panel View]
│   │   │   │       ├── UploadModal
│   │   │   │       └── UploadProgressModal
```

### Navigation Flow

```javascript
// Simplified state management in Dashboard.jsx
const [viewState, setViewState] = useState({
  type: 'GLOBAL', // 'GLOBAL' | 'COMPANY' | 'DOCUMENT'
  data: { company: null, document: null }
})

// Navigation handlers
handleCompanySelect(company)  → { type: 'COMPANY', data: { company, document: null } }
handleDocumentSelect(document) → { type: 'DOCUMENT', data: { company, document } }
handleBackToGlobal()          → { type: 'GLOBAL', data: { company: null, document: null } }
handleBackToCompany()         → { type: 'COMPANY', data: { company, document: null } }
```

### Key Design Principles

1. **Single Source of Truth**: `Dashboard.jsx` owns all navigation state
2. **View Composition**: Each state defines both left and right panel content
3. **Context for Cross-Cutting Concerns**: Auth, theme, and uploads are managed globally
4. **Modal Separation**: Global interactions (uploads) are handled as modals, not inline views
5. **Hierarchical Navigation**: Breadcrumbs reflect the state hierarchy and enable backward navigation

### Frontend File Inventory

The following is a comprehensive list of all frontend files and their roles. Files marked with ⚠️ contain legacy/spaghetti code that needs refactoring.

#### Entry Point & Configuration
- **`main.jsx`**: Application entry point, renders `App.jsx` into DOM
- **`App.jsx`**: Root component, sets up provider hierarchy and routing
- **`App.css`**: Minimal root-level styles
- **`config.js`**: API base URL and configuration constants
- **`index.css`**: Global CSS variables, resets, and base styles

#### Pages
- **`pages/LoginPage.jsx`**: Email/Password login page with secondary Google OAuth support
- **`pages/LoginPage.css`**: Login page styles
- **`pages/Dashboard.jsx`**: Central orchestrator for the three-state user journey

#### Contexts (Global State)
- **`contexts/AuthContext.jsx`**: Authentication state, token management, 401 interceptor
- **`contexts/ThemeContext.jsx`**: Light/dark theme state and persistence
- **`contexts/UploadContext.jsx`**: Real-time upload status management via SSE

#### Layout Components
- **`components/layout/Header.jsx`**: Persistent header with user profile, theme toggle, logout
- **`components/layout/Header.css`**: Header styles
- **`components/layout/SplitScreen.jsx`**: Draggable split-panel layout (20-80% range)
- **`components/layout/SplitScreen.css`**: Split screen styles

#### Modal Components
- **`components/modals/UploadModal.jsx`**: File upload dialog (drag-and-drop + picker)
- **`components/modals/UploadModal.css`**: Upload modal styles
- **`components/modals/UploadProgressModal.jsx`**: Real-time upload progress tracking

#### View Components - Global (State 1)
- **`components/views/global/CompanyList.jsx`**: Searchable company list (left panel)
- **`components/views/global/WelcomeView.jsx`**: Welcome screen with recent activity (right panel)
- **`components/views/global/Dashboard.css`**: Global view styles

#### View Components - Company (State 2)
- **`components/views/company/DocumentList.jsx`**: Document list for selected company (left panel)
- **`components/views/company/CompanyAnalysisView.jsx`**: Company metrics and DCF model (right panel)
- **`components/views/company/FinancialModel.jsx`**: DCF valuation model component
- **`components/views/company/FinancialModel.css`**: Financial model styles
- **`components/views/company/Company.css`**: Company view styles

#### View Components - Document (State 3)
- **`components/views/document/DocumentView.jsx`**: Document metadata and PDF viewer (left panel)
- **`components/views/document/DocumentExtractionView.jsx`**: Extracted financial data tables (right panel)
- **`components/views/document/Document.css`**: Document view styles

#### Custom Hooks
- **`hooks/useUploadManager.js`**: Manages upload modal state and duplicate handling logic
- **`hooks/useDashboardData.js`**: Fetches and filters company list data
- **`hooks/useDocumentData.js`** ⚠️: Fetches document data, extraction status, and financial tables
  - **Refactoring Needed**: Large hook (~320 lines) that manages too many concerns. Should be split into:
    - `useDocumentMetadata.js` (basic document info)
    - `useExtractionData.js` (balance sheet, income statement)
    - `useCalculationData.js` (historical calculations)
- **`hooks/usePdfViewer.js`**: Manages PDF viewer state and rendering
- **`hooks/useAnalysisEvents.js`**: WebSocket/polling for real-time analysis status updates

#### Utility Functions
- **`utils/formatting.js`**: Number formatting, currency, percentages
- **`utils/textUtils.js`**: Text manipulation utilities
- **`utils/textUtils.test.js`**: Tests for text utilities

#### Styles
- **`styles/layout.css`**: Layout-specific styles (panels, containers)
- **`styles/components.css`**: Shared component styles (buttons, tables, badges)
- **`styles/components_temp.css`** ⚠️: Legacy/temporary styles
  - **Refactoring Needed**: This file contains orphaned styles that should either be migrated to proper component CSS files or deleted.

#### Tests
- **`test/setup.js`**: Vitest test configuration
- **`__tests__/app-routes.test.jsx`**: Routing tests
- **`__tests__/app-smoke.test.jsx`**: Basic smoke tests
- **`__tests__/dashboard-render.test.jsx`**: Dashboard rendering tests
- **`__tests__/header.test.jsx`**: Header component tests
- **`hooks/__tests__/useDashboardData.test.jsx`**: Dashboard data hook tests

#### Known Technical Debt

1. **useDocumentData.js** (High Priority)
   - **Issue**: God hook that manages document metadata, extractions, and calculations
   - **Impact**: Difficult to test, violates single responsibility principle
   - **Solution**: Split into focused hooks as described above

3. **components_temp.css** (Medium Priority)
   - **Issue**: Orphaned temporary styles
   - **Impact**: Unclear which styles are actually used
   - **Solution**: Audit usage, migrate to proper files, delete unused styles

4. **Inline API Calls** (Medium Priority)
   - **Issue**: Some components make direct axios calls instead of using hooks
   - **Impact**: Harder to mock for testing, inconsistent patterns
   - **Solution**: Centralize all API calls in custom hooks or a dedicated API service layer

5. **Missing Component Tests** (Low Priority)
   - **Issue**: Most view components lack unit tests
   - **Impact**: Regression risk during refactoring
   - **Solution**: Add tests incrementally, prioritize complex components

## Login Page

### Purpose

The login page is the landing page during development and is the gateway to the shared dashboard.

### User Flow

1. User arrives on login page
2. User enters Email and Password OR clicks **Sign in with Google**
3. Backend verifies credentials and returns a JWT (App Token)
4. Application stores token in LocalStorage
5. User lands in the Global Dashboard (two-panel layout)

### UI Requirements

#### Login Forms
- Email and Password inputs with validation
- Primary **Login** button
- Secondary **Sign in with Google** button
- "Sign Up" toggle for new account creation

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

> **Note**: For detailed frontend architecture and state management, see the [Frontend Architecture](#frontend-architecture) section above.

### Two Adjustable Split Screens

- Vertical split with draggable divider
- Min/max widths: **20% / 80%**
- Default split: **50% / 50%**
- Split preference stored in localStorage per user

### Panel Content Summary

> **Note**: See [State 1](#state-1-global-dashboard-home), [State 2](#state-2-company-overview), and [State 3](#state-3-document-analysis) in the Frontend Architecture section above for detailed panel content specifications.

### UI Components

#### Header (Persistent)
- Application logo/title
- User profile (name, avatar)
- Theme toggle (day/night mode)
- Logout button

#### Breadcrumb Navigation
- Reflects current state hierarchy
- Clickable links to navigate back
- Examples:
  - State 1: `Companies`
  - State 2: `< Companies › [Company Name]`
  - State 3: `< [Company Name] › [Document Name]`

#### Action Buttons
- **Add Document**: Opens upload modal
  - Available in State 1 (Global) and State 2 (Company)
  - Pre-selects company when triggered from State 2
- **Check Uploads**: Replaces "Add Document" when uploads are active
  - Shows upload progress modal
  - Available across all states

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

**Ingestion Milestones**
1. Uploading
2. Classification (with Ticker Reflection)
3. Indexing (with Gemini Summarization)

**Extraction Milestones (Conditional)**
1. Extracting Balance Sheet
2. Extracting Income Statement
3. Extracting Additional Items (Shares, Growth)
4. Classifying Non-Operating Items

**States**
- Completed: green check
- Active: highlighted with pulse animation
- Pending: muted/gray
- Error/Warning: contextual indicators

### Duplicate Detection UX

- Progress halts at **Classification**
- Warning banner appears
- Shows existing document metadata
- **Replace & Index** button resumes pipeline

### Financial Statement Processing (Document View)

When a document is selected:

When a document is selected:

- **Mission Control (Intelligence Stream)**: Accessible via the "Check Status" button.
- **Extraction Milestones**:
  1. Extracting & classifying balance sheet (with Stage 2 self-correction).
  2. Extracting & classifying income statement (with Stage 2 self-correction).
  3. Extracting additional items (Shares, Organic Growth).
  4. Classifying non-operating items (Tiger-Transformer validation).
- **Gemini Feedback**: Real-time extraction summaries (e.g., "Successfully parsed 42 line items. Currency detected: USD") are displayed as rich messages in the stream.
- **Standardization**: Highlighting when the Tiger-Transformer model maps ad-hoc names to unified operating categories.

## Historical Metrics & Analysis

The application automatically computes and displays the following based on extracted data:

### 1. Invested Capital
- **Net Working Capital**: Operating Current Assets - Operating Current Liabilities.
  - Breakdowns for components.
- **Net Long-Term Operating Assets**: Operating Non-Current Assets - Operating Non-Current Liabilities.
- **Total Invested Capital**: Sum of the above.

### 2. EBITA & Margins
- **EBITA**: Operating Income adjusted for non-operating items and amortization.
- Breakdown of non-GAAP adjustments.

### 3. Adjusted Tax Rate
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

#### Enterprise Value Calculation
- **Enterprise Value**: Sum of PV of 10-year forecast FCFs + PV of Terminal Value.
- **Discounting**: Uses **Mid-Year Convention** for cash flows.

#### Equity Value Bridge
The model calculates **Equity Value** from **Enterprise Value** using non-operating items:
- **Add**: Cash, Short Term Investments, Other Financial or Physical Assets
- **Subtract**: Debt, Other Financial Liabilities, Preferred Equity, Minority Interest
- **Result**: Value of Common Equity

#### Fair Value per Share
- **Diluted Shares Outstanding**: Fetched from most recent quarterly data
- **Fair Value per Share**: Equity Value / Diluted Shares Outstanding
- **Current Share Price**: Real-time market price (fetched via API)
- **Percent Undervalued (or Overvalued)**: (Fair Value - Current Price) / Current Price
  - Positive = Undervalued (green)
  - Negative = Overvalued (red)

#### Past Valuations Tracking
- **Save Valuation**: Button to snapshot current fair value estimate
- **Past Valuations Table**: Historical record of all saved valuations
  - Columns: Date, User, Fair Value per Share, Share Price at Time, % Diff, Delete
  - Sorted by date (most recent first)
  - Allows comparison of valuation changes over time
  - User attribution for collaborative tracking

#### Interactive UI
- **Re-run Valuation**: Triggers server-side recalculation using current assumptions
- **Reset Assumptions**: Reverts to system-calculated defaults (L4Q averages)
- **Save Valuation**: Persists current valuation snapshot to database

#### Data Sources
- **Non-Operating Items**: Classified by `non_operating_classifier.py` agent
- **Share Price**: Fetched from market data API
- **Diluted Shares**: Extracted from most recent quarterly filing
- **Time Period Selection**: Uses most recent fiscal quarter (not most recently updated document)
