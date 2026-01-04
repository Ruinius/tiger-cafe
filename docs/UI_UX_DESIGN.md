# Tiger-Cafe UI/UX Design Guide

**A private project for Tiger and his friends to play with AI agents performing financial analysis.**

This document captures the UI/UX requirements for the Tiger-Cafe application, with emphasis on the shared dashboard workflow and document processing lifecycle.

## Design Principles

1. **Day/night mode** with a persistent toggle.
2. **Two-panel workspace** after login (adjustable split screens).
3. **Shared global dashboard**: every authenticated user sees the same workspace.
4. **Attribution-only authentication**: login is used to track who did what, not to isolate data.

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

### Right Panel (Content)

- Default: recent completed analysis list
- Company selected: company analysis dashboard
- Document selected: extracted data + progress view
  - Financial statements tables
  - Validation indicators
  - Operating vs. non-operating classification
  - Additional items table
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

- Progress tracker shows **5 milestones**:
  1. Extracting balance sheet
  2. Classifying balance sheet
  3. Extracting income statement
  4. Extracting additional items
  5. Classifying income statement
- Real-time status: `checking`, `pending`, `in_progress`, `completed`, `error`, `not_found`
- Tables include validation status and operating/non-operating labels

#### 3. Document Status Indicators
- Status badges with color coding:
  - Pending: Gray badge "Pending"
  - Indexing: Blue badge with spinner "Indexing..."
  - Indexed: Green badge "Indexed"
  - Processing Analysis: Orange badge "Analyzing..."
  - Analysis Complete: Green badge "Complete"
  - Error: Red badge "Error" with tooltip showing error message
- Progress bar for indexing (0-100%)
- Icon indicators: Checkmark (complete), spinner (processing), X (error)
- Status tooltip on hover showing detailed status
- Real-time updates visible to all users

#### 4. Financial Analysis Trigger
- Button placement: In document row or company detail header
- Button label: "Run Analysis" or "Analyze Document"
- Confirmation dialog: "Start financial analysis for [Document Name]? This may take several minutes."
- Disabled state: Gray out button and show tooltip "Analysis already in progress" or "Analysis completed"
- Attribution display: Show "Analyzed by [User Name]" with timestamp after completion
- Real-time updates:
  - Show progress indicator when analysis starts
  - Display "Analysis in progress..." status
  - Update all users' views when analysis completes
  - Show notification toast when analysis finishes
- Multiple documents: Allow bulk analysis trigger with checkbox selection

## Phase 5: Financial Statement Processing UI/UX

### User Flow
1. User selects a document in the left panel (earnings announcement, quarterly filing, or annual report)
2. Right panel displays financial statement view with progress tracker
3. Progress tracker shows 5 milestones with real-time status:
   - Extracting Balance Sheet (checking/pending/in_progress/completed/error/not_found)
   - Classifying Balance Sheet (checking/pending/in_progress/completed/error/not_found)
   - Extracting Income Statement (checking/pending/in_progress/completed/error/not_found)
   - Extracting Additional Items (checking/pending/in_progress/completed/error/not_found)
   - Classifying Income Statement (checking/pending/in_progress/completed/error/not_found)
4. Once all milestones are terminal (completed/error/not_found), financial statements load
5. Balance sheet and income statement tables display with all line items, categories, amounts, units, and operating/non-operating classification
6. Additional Items table displays: prior period revenue, YOY revenue growth, amortization, basic shares outstanding, diluted shares outstanding (each with units)
7. Historical Calculations table displays: Net Working Capital, Net Long Term Operating Assets, Invested Capital, Capital Turnover, Annualized, EBITA, EBITA Margin, Effective Tax Rate (monetary values with units, ratios/percentages with "—")
8. Validation status shown (valid or with error details)
9. Key totals are bolded for emphasis
10. Units displayed in headers (to the right of Currency) and in table columns as appropriate

### UI Components Needed

#### 1. Financial Statement Display (Right Panel)
- **Header Section**:
  - Title: "Financial Statements"
  - Progress tracker displayed first (always visible when document is selected)
- **Progress Tracker**:
  - Shows all 5 milestones with status indicators
  - Status values: checking (default), pending (processing), in_progress, completed, error, not_found
  - Icons: ✓ (completed), ⟳ (in_progress/checking), ✗ (error), ○ (not_found/pending)
  - Color coding: Green (completed), Blue (in_progress), Red (error), Gray (checking/not_found)
  - Message display for each milestone
  - Polling every 3 seconds for updates
- **Eligibility Check**:
  - Only shows for earnings announcements, quarterly filings, and annual reports
  - Shows informational message for other document types
- **Loading Logic**:
  - Progress tracker always shown first
  - If any milestone is pending/in_progress, do not load financial statements
  - Once all milestones are terminal (completed/error/not_found), load financial statements
  - Maximum 3 load attempts before showing "nothing to see here"

#### 2. Balance Sheet Table
- **Header Section**:
  - Time Period, Currency, Unit (displayed to the right of Currency)
  - Unit values: ones, thousands, millions, billions, or ten thousands (for foreign stocks)
- **Table Structure**:
  - Columns: Line Item, Category, Amount (right-aligned), Type
  - Responsive table with horizontal scroll if needed
  - Sticky header on scroll
- **Line Item Display**:
  - All balance sheet line items in order
  - Currency-formatted amounts
  - Category labels (Current Assets, Total Assets, etc.)
  - Operating/Non-Operating badges with color coding
- **Key Totals Highlighting**:
  - Total Assets: Bold text
  - Total Liabilities: Bold text
  - Total Stockholder's Equity: Bold text
  - Total Liabilities and Stockholder's Equity: Bold text
  - No background highlighting (clean appearance)
- **Table Styling**:
  - Alternating row colors on hover
  - Clean borders and spacing
  - Monospace numbers for alignment

#### 3. Income Statement Table
- **Header Section**:
  - Time Period, Currency, Unit (displayed to the right of Currency)
  - Unit values: ones, thousands, millions, billions, or ten thousands (for foreign stocks)
- **Table Structure**:
  - Columns: Line Item, Category, Amount (right-aligned), Type
  - Responsive table with horizontal scroll if needed
  - Sticky header on scroll
- **Line Item Display**:
  - All income statement line items in order
  - Currency-formatted amounts
  - Category labels (Revenue, Costs, Expenses, etc.)
  - Operating/Non-Operating badges with color coding
- **Key Totals Highlighting**:
  - Total Assets: Bold text
  - Total Liabilities: Bold text
  - Total Stockholder's Equity: Bold text
  - Total Liabilities and Stockholder's Equity: Bold text
  - No background highlighting (clean appearance)
- **Table Styling**:
  - Alternating row colors on hover
  - Clean borders and spacing
  - Monospace numbers for alignment

#### 4. Additional Items Table
- **Table Structure**:
  - Title: "Additional Items"
  - Columns: Item, Value, Unit
  - Displays after income statement
- **Items Displayed**:
  - Prior Period Revenue (with unit)
  - YOY Revenue Growth (percentage, unit shows "—")
  - Amortization (with unit)
  - Basic Shares Outstanding (with unit, usually "ones")
  - Diluted Shares Outstanding (with unit, usually "ones")
- **Unit Display**:
  - Each item has its own unit field
  - Units displayed in separate column to the right of Value
  - Percentages show "—" for unit
- **Styling**:
  - Clean table format matching balance sheet and income statement styling
  - Currency/number formatting as appropriate

#### 5. Historical Calculations Table
- **Table Structure**:
  - Title: "Historical Calculations"
  - Columns: Metric, Value, Unit
  - Displays after income statement and additional items
  - Section separated with border-top for visual distinction
- **Metrics Displayed**:
  - Net Working Capital (with unit)
  - Net Long Term Operating Assets (with unit)
  - Invested Capital (with unit)
  - Capital Turnover, Annualized (ratio, unit shows "—"; quarterly revenue is annualized by multiplying by 4)
  - EBITA (with unit)
  - EBITA Margin (percentage, unit shows "—")
  - Effective Tax Rate (percentage, unit shows "—")
- **Unit Display**:
  - Monetary values use the balance sheet/income statement unit
  - Ratios and percentages show "—" for unit
  - Units displayed in separate column to the right of Value
- **Styling**:
  - Clean table format matching other financial statement tables
  - Currency/number formatting as appropriate

#### 6. Validation Status Display
- **Valid Balance Sheet**:
  - Green validation badge
  - No error messages shown
- **Invalid Balance Sheet**:
  - Red validation badge
  - Error section with list of validation errors:
    - Current assets sum mismatch
    - Total assets sum mismatch
    - Current liabilities sum mismatch
    - Total liabilities sum mismatch
    - Balance sheet equation mismatch (Assets ≠ Liabilities + Equity)
- **Error Formatting**:
  - Clear, readable error messages
  - Bulleted list format
  - Red color scheme for visibility

#### 7. Operating/Non-Operating Classification
- **Type Badges**:
  - Operating: Green badge with light green background
  - Non-Operating: Orange badge with light orange background
  - Displayed in "Type" column for each line item
- **Classification Logic**:
  - Uses LLM with balance_sheet_items.csv as reference
  - LLM uses best judgment for classification
  - Persisted in database and displayed in UI

#### 8. Processing Workflow
- **Automatic Processing**:
  - Financial statement processing automatically starts after document indexing completes
  - Processing runs sequentially: balance sheet first, then income statement
  - No manual trigger needed
- **Re-run Functionality**:
  - "Re-run Extraction and Classification" button in document detail view (left panel)
  - Re-runs entire pipeline (balance sheet + income statement)
  - Immediately sets all milestones to pending and starts polling
  - Button disabled during processing
  - Clears financial statement data before re-running
- **Delete Functionality**:
  - "Delete Financial Statements" button: Removes all financial statement data
  - "Delete Document" button: Permanently deletes document and all associated data
  - Buttons located in document detail view (left panel)
  - Delete Document button navigates back to company document list after deletion
- **Background Processing**:
  - Embedding-based location of financial statement sections
  - Document-level pre-filtering to optimize API calls
  - LLM extraction of line items
  - Validation with up to 3 retry attempts
  - Operating/non-operating classification
  - Real-time status updates via polling (every 3 seconds)
- **Completion**:
  - Tables automatically display when all milestones are terminal
  - Validation status shown immediately
  - User can view full financial statement data

### Design Specifications

#### Balance Sheet Table
- Font size: 0.875rem (14px) for table content
- Header: Bold, sticky, background color var(--bg-secondary)
- Row hover: Subtle background color change
- Key totals: Bold text (font-weight: 700), no background highlighting
- Currency formatting: Right-aligned, tabular numbers
- Borders: 1px solid var(--border) between rows, 2px for header

#### Status Indicators
- Processing: Spinner animation with "Processing balance sheet..." text
- Valid: Green badge with checkmark
- Invalid: Red badge with X, error list below
- Button states: Enabled (primary color), Disabled (grayed out)

#### Responsive Behavior
- Table scrolls horizontally on smaller screens
- Metadata wraps on mobile devices
- Button full-width on mobile, auto-width on desktop

## Phase 6: Financial Metrics Display UI/UX

### User Flow
1. User views **shared** list of companies with pending/completed analysis (all users see the same data)
2. User selects a company with completed analysis
3. System displays financial metrics, valuation model, sensitivity analysis, and LLM summaries
4. Attribution shows who initiated each analysis
5. All users can interact with and modify the same valuation models and sensitivity analyses

### UI Components Needed

#### 1. Financial Metrics Display
- Metric cards: Grid layout showing key metrics (Revenue, Operating Margin, Growth Rate, etc.)
- Trend charts: Line charts showing metric trends over time periods
- Time period selection: Dropdown or tabs (Quarterly, Annual, Custom range)
- Comparison views: Side-by-side comparison of different time periods
- Metric cards show:
  - Metric name
  - Current value (large, prominent)
  - Previous period value (for comparison)
  - Change indicator (up/down arrow with percentage)
  - Color coding: Green (positive), Red (negative), Gray (neutral)
- Interactive charts: Hover to see exact values, click to drill down
- Export options: Download charts as images or data as CSV

#### 2. Interactive Valuation Model
- Input fields: Form layout with labeled inputs for key assumptions:
  - Growth rate (percentage)
  - Discount rate (WACC)
  - Terminal growth rate
  - Operating margin assumptions
  - Other model-specific parameters
- Real-time calculation: Update valuation results as user types (debounced)
- Model visualization:
  - DCF model breakdown (cash flows, terminal value, present value)
  - Valuation range display (low, base, high scenarios)
  - Sensitivity chart showing impact of assumption changes
- Save functionality: "Save Scenario" button to save current assumptions
- Reset functionality: "Reset to Defaults" button to restore original assumptions
- Show attribution: "Last modified by [User Name] at [Timestamp]"
- Multiple scenarios: Allow users to create and compare different scenarios

#### 3. Sensitivity Analysis UI
- Adjustable controls: Sliders or number inputs for key assumptions
- Sensitivity table: Matrix showing valuation outcomes across assumption ranges
- Visualization options:
  - Heatmap: Color-coded matrix (green = high value, red = low value)
  - 3D surface chart: Interactive 3D visualization of sensitivity
  - Tornado chart: Bar chart showing impact of each assumption
- Real-time updates: Table and charts update as sliders move
- Range selection: Allow users to set min/max ranges for assumptions
- Export: Download sensitivity table as CSV or image
- Tooltips: Hover over cells to see exact values and assumptions

#### 4. LLM Summary Display
- Summary card layout: Card-based design with clear sections
- Content sections:
  - Executive Summary (collapsible)
  - Key Findings (bullet points)
  - Financial Highlights
  - Risk Factors
  - Recommendations
- Source attribution:
  - "Generated from [Document Type] - [Document Name]"
  - "Analysis date: [Timestamp]"
  - "Based on data from [Time Period]"
- Expandable sections: Click to expand/collapse each section
- Refresh/regenerate: "Regenerate Summary" button with loading state
- Show confidence indicators if available
- Copy to clipboard functionality for easy sharing
- Print-friendly formatting option

## Design System

### Color Palette

#### Primary Colors
- Primary: Blue (#4285F4) - Main actions, links, highlights
- Primary Dark: Dark Blue (#1976D2) - Hover states, active elements
- Primary Light: Light Blue (#64B5F6) - Subtle highlights

#### Secondary Colors
- Secondary: Gray (#757575) - Secondary text, borders
- Secondary Dark: Dark Gray (#424242) - Headers, emphasis
- Secondary Light: Light Gray (#E0E0E0) - Dividers, backgrounds

#### Status Colors
- Success: Green (#4CAF50) - Completed states, positive indicators
- Warning: Orange (#FF9800) - Warnings, pending states
- Error: Red (#F44336) - Errors, negative indicators
- Info: Blue (#2196F3) - Informational messages

#### Background Colors (Day Mode)
- Background: White (#FFFFFF)
- Surface: Light Gray (#F5F5F5)
- Paper: White (#FFFFFF)

#### Background Colors (Night Mode)
- Background: Dark Gray (#121212)
- Surface: Darker Gray (#1E1E1E)
- Paper: Dark Gray (#2C2C2C)

#### Text Colors (Day Mode)
- Primary Text: Dark Gray (#212121)
- Secondary Text: Medium Gray (#757575)
- Disabled Text: Light Gray (#BDBDBD)

#### Text Colors (Night Mode)
- Primary Text: Light Gray (#E0E0E0)
- Secondary Text: Medium Gray (#BDBDBD)
- Disabled Text: Dark Gray (#616161)

### Typography

#### Font Families
- Primary: System font stack (San Francisco, Segoe UI, Roboto, sans-serif)
- Monospace: 'Courier New', 'Monaco', monospace (for code/data)

#### Font Sizes
- H1 (Page Title): 32px / 2rem
- H2 (Section Title): 24px / 1.5rem
- H3 (Subsection): 20px / 1.25rem
- H4 (Card Title): 18px / 1.125rem
- Body Large: 16px / 1rem
- Body: 14px / 0.875rem
- Body Small: 12px / 0.75rem
- Caption: 10px / 0.625rem

#### Font Weights
- Light: 300
- Regular: 400
- Medium: 500
- Semi-bold: 600
- Bold: 700

#### Line Heights
- Tight: 1.2 (for headings)
- Normal: 1.5 (for body text)
- Relaxed: 1.75 (for long-form content)

### Spacing and Layout

#### Grid System
- 8px base unit for spacing
- 12-column grid system for layouts
- Gutter: 16px between columns

#### Padding/Margin Standards
- XS: 4px (0.25rem)
- SM: 8px (0.5rem)
- MD: 16px (1rem)
- LG: 24px (1.5rem)
- XL: 32px (2rem)
- XXL: 48px (3rem)

#### Component Spacing
- Card padding: 16px (MD)
- Button padding: 8px 16px (SM horizontal, MD vertical)
- Input padding: 12px 16px
- Section spacing: 24px (LG) between sections
- List item spacing: 8px (SM) between items

#### Breakpoints for Responsive Design
- Mobile: < 768px
- Tablet: 768px - 1024px
- Desktop: > 1024px
- Large Desktop: > 1440px

### Components Library

#### Buttons
- Primary: Solid background, primary color
- Secondary: Outlined border, transparent background
- Text: Text-only, no background
- Icon: Circular/square with icon only
- Sizes: Small (32px), Medium (40px), Large (48px)
- States: Default, Hover, Active, Disabled, Loading

#### Cards
- Standard card: White background, subtle shadow, rounded corners (8px)
- Elevated card: Higher shadow for emphasis
- Interactive card: Hover elevation increase
- Card header: Bold title with optional actions
- Card content: Padding 16px
- Card footer: Optional footer with actions

#### Forms
- Input fields: Label above, placeholder text, error states
- Text areas: Multi-line with auto-resize
- Select dropdowns: Custom styled, searchable
- Checkboxes: Custom styled with labels
- Radio buttons: Custom styled groups
- Form validation: Inline error messages below fields

#### Tables
- Header: Bold, sticky on scroll
- Rows: Alternating row colors, hover highlight
- Cells: Padding 12px, text alignment options
- Sortable columns: Arrow indicators
- Responsive: Horizontal scroll on mobile

#### Modals
- Overlay: Semi-transparent dark background
- Modal: Centered, max-width 600px, rounded corners
- Header: Title with close button
- Body: Scrollable content area
- Footer: Action buttons (Cancel, Confirm)

#### Progress Indicators
- Linear progress bar: Horizontal bar with percentage
- Circular spinner: For loading states
- Step indicator: For multi-step processes
- Skeleton screens: For content loading

#### Status Badges
- Pill-shaped badges with rounded corners
- Color-coded by status type
- Icon + text or text only
- Sizes: Small, Medium

#### Navigation
- Breadcrumbs: Horizontal navigation trail
- Tabs: Horizontal tab navigation
- Sidebar: Vertical navigation menu
- Pagination: Page numbers with prev/next

#### Data Visualization
- Charts: Line, bar, pie, area charts
- Tooltips: Hover information on data points
- Legends: Color-coded legend for chart data
- Axes: Labeled X and Y axes

## Wireframes and Mockups

<!-- Add links to wireframes, mockups, or design files here -->
<!-- Or describe the layout and component placement -->

## Accessibility Considerations

### Keyboard Navigation
- All interactive elements must be keyboard accessible
- Tab order follows visual flow
- Enter/Space to activate buttons and links
- Arrow keys for navigation in lists and menus
- Escape to close modals and dropdowns
- Focus indicators: Clear visible outline (2px, primary color)

### Screen Reader Support
- Semantic HTML elements (nav, main, article, section)
- ARIA labels for icon-only buttons
- ARIA live regions for dynamic content updates
- Alt text for all images and charts
- Form labels properly associated with inputs
- Error messages announced to screen readers

### Color Contrast Requirements
- Text on background: Minimum 4.5:1 contrast ratio (WCAG AA)
- Large text (18px+): Minimum 3:1 contrast ratio
- Interactive elements: Minimum 3:1 contrast ratio
- Status indicators: Use icons/shapes in addition to color

### ARIA Labels
- Buttons: aria-label for icon buttons
- Forms: aria-describedby for error messages
- Navigation: aria-current for active page
- Modals: aria-modal="true", aria-labelledby for title
- Status: aria-live="polite" for dynamic updates
- Loading: aria-busy="true" during async operations

### Additional Accessibility Features
- Skip to main content link
- Focus management in modals (trap focus, return focus on close)
- Reduced motion support (respect prefers-reduced-motion)
- High contrast mode support

## Notes and Decisions

### Shared Global Dashboard Decision
- **Decision**: All users work on the same global dashboard with no user-specific data isolation
- **Rationale**: Enables collaboration and shared knowledge base
- **Implications**: 
  - Login is only for attribution tracking, not access control
  - All users see all companies, documents, and analyses
  - Real-time updates are visible to all users
  - Attribution is displayed for transparency

### Two Split Screens Layout
- **Decision**: Workspace uses two adjustable split screens
- **Rationale**: Allows users to view multiple pieces of information simultaneously
- **Implementation**: User-adjustable split with draggable divider

### Day/Night Toggle
- **Decision**: Users can toggle between day and night modes
- **Rationale**: Improves usability and reduces eye strain
- **Implementation**: Preference stored per user, but applies to shared dashboard

<!-- Add any additional UI/UX decisions, trade-offs, or notes as the design evolves -->

## Visual Summary Checklist

- [ ] Shared global dashboard (no per-user data)
- [ ] Attribution visible in lists and details
- [ ] Two-panel adjustable layout
- [ ] Upload flow with progress + duplicate handling
- [ ] Day/night toggle with persistence
