# Tiger-Cafe UI/UX Design Guide

**A private project for Tiger and his friends to play with AI agents performing financial analysis.**

This document outlines the user interface and user experience design specifications for Tiger-Cafe.

## Design Principles
1. Day and night toggle options
2. After successful login, all the workspace is two adjustable split screens
3. **Shared Global Dashboard**: All users work on the same global dashboard - no user-specific views or data isolation
4. **Login Purpose**: Authentication is only used to track attribution (who uploaded documents and initiated analyses)

## Global Dashboard Architecture

### Overview
The Tiger-Cafe application uses a **shared global dashboard** where all authenticated users see and interact with the same data. Users can view all companies, documents, and analyses regardless of who uploaded or created them. Login serves purely for **attribution tracking** - to record which user performed which actions.

### Key Implications
- **No user filtering**: Users see all companies and documents in the system
- **Attribution display**: UI shows who uploaded documents and who initiated analyses (for transparency and collaboration)
- **Collaborative workspace**: Multiple users can work on the same companies and analyses simultaneously
- **Shared state**: All users see real-time updates from all other users

### Attribution Display

User name next to uploaded documents
User name next to initiated analyses
Timestamp of actions



## Login Page

### Purpose
During development, the landing page is the login page.
The login page allows users to authenticate using their Google account via OAuth. This is the entry point for authenticated users.

### User Flow
1. User arrives at login page (from landing page or direct navigation)
2. User clicks "Sign in with Google" button
3. User is redirected to Google OAuth consent screen
4. User grants permissions
5. User is redirected back to Tiger-Cafe
6. User is authenticated and redirected to main application (company list or dashboard)

### UI Components Needed

#### 1. Login Form/Interface
Centered card for the Google login.
There is nothing else.

#### 2. Google OAuth Button
- Follow Google's branding guidelines for "Sign in with Google" button
- Standard button size: minimum 240px width, 40px height
- Google logo icon on the left side of button text
- Button text: "Sign in with Google"
- Hover state: slight elevation/shadow increase
- Active state: slight press animation
- Use Google's official brand colors (blue #4285F4)
- Button should be clearly visible and accessible

#### 3. Error Handling
- Display error messages in a non-intrusive banner or toast notification
- Use clear, user-friendly language (avoid technical jargon)
- Common error scenarios:
  - OAuth cancellation: "Sign in was cancelled. Please try again."
  - Network error: "Unable to connect. Please check your internet connection."
  - Server error: "Something went wrong. Please try again later."
- Error messages should be dismissible
- Provide retry option when applicable
- Log technical details server-side for debugging

#### 4. Loading States
- Show loading spinner or skeleton screen during OAuth redirect
- Display "Signing you in..." message during authentication processing
- Smooth fade-in transition when redirecting to dashboard
- Loading indicator should be centered and clearly visible
- Prevent multiple clicks during loading state

#### 5. Post-Login Redirect
After successful login, users are redirected to the **Global Dashboard** with the two adjustable split screens layout. All users see the same shared workspace regardless of who logged in.

## Global Dashboard Layout

### Two Adjustable Split Screens
After successful login, the entire workspace consists of two adjustable split screens that can be resized by the user.

#### Split Screen Configuration
1. Split is vertical.
2. Resizing is a draggable divider
3. Minimum and maximum sizes are 20% and 80%
4. Default split ratio is 50%
5. Split preference is per user

#### Left/First Panel
In general, the left side is a robust navigation with breadcrumbs showing the raw data and document
1. List of companies (default view)
2. There is an "Add Document" button on the bottom to initiate the add document flow
3. During active uploads, button changes to "Check Uploads" with spinner
4. Clicking "Check Uploads" shows upload progress view with list of uploading documents
5. Clicking into the company shows a list of underlying documents on the left and updates the right with analysis for the company
6. Clicking into a document shows the underlying document on the left and the relevant extractions on the right

#### Right/Second Panel
1. Default is a home page with a list of the latest completed company analysis
2. The page with all the company analysis if a company is selected
3. Extracted information from the document if one is selected on the left panel:
   - For eligible documents (earnings announcements, quarterly filings, annual reports): Financial statements display
   - Progress tracker showing 5 milestones with real-time status updates
   - Balance sheet table with line items, validation status, and operating/non-operating classification
   - Income statement table with line items, validation status, and operating/non-operating classification
   - Additional Items table with: prior period revenue, YOY revenue growth, amortization, basic shares outstanding, diluted shares outstanding
   - Re-run and delete buttons in document detail view (left panel)

### Day/Night Toggle
- Toggle button placement: Top-right corner of the header/navbar
- Visual design: Icon toggle (sun/moon icons) or switch component
- Day mode color scheme:
  - Background: Light gray/white (#FFFFFF, #F5F5F5)
  - Text: Dark gray/black (#212121, #000000)
  - Accent: Primary brand color
- Night mode color scheme:
  - Background: Dark gray/black (#121212, #1E1E1E)
  - Text: Light gray/white (#E0E0E0, #FFFFFF)
  - Accent: Lighter shade of primary brand color
- Smooth transition: 200-300ms fade transition between modes
- Persistence: Preference stored per user in browser/localStorage
- Apply theme immediately on page load based on saved preference

## Phase 2: Document Upload and Classification UI/UX

### User Flow (New Multi-Document Upload Workflow)
1. User clicks "Add Document" button in left panel
2. Modal opens with drag-and-drop interface for multiple documents (up to 10 files)
3. User drags and drops or selects multiple PDF files (up to 10)
4. Modal closes immediately after files are selected
5. **Upload step**: Files are saved in parallel (file I/O only, no API calls)
6. **Classification & Indexing**: Documents are queued for sequential processing (one at a time) to prevent API overload
7. "Add Document" button transforms into "Check Uploads" button with spinning indicator while uploads are in progress
8. User can click "Check Uploads" to view upload progress
9. Left panel shows list of uploading documents with progress bars and milestones
10. If duplicate detected, progress stops before indexing and shows warning with "Replace & Index" button
11. If no duplicate, indexing proceeds automatically through the sequential queue
12. After indexing completes, financial statement processing automatically starts (if eligible)
13. Attribution shows who uploaded each document

### UI Components Needed

#### 1. Multi-Document Upload Modal
- Drag-and-drop interface supporting up to 10 PDF files
- Clear indication of file limit: "Upload up to 10 PDF documents"
- Visual drop zone with dashed border
- File list showing selected files before upload
- Remove file option for each selected file
- "Upload" button to start the process
- Modal closes immediately after files are selected and upload starts
- All processing happens asynchronously in background

#### 2. Add Document / Check Uploads Button
- Default state: "Add Document" button
- Active upload state: "Check Uploads" button with spinning indicator
- Button located at bottom of left panel
- Spinner indicates active uploads in progress
- Clicking "Check Uploads" switches left panel to upload progress view

#### 3. Upload Progress View (Left Panel)
- Replaces company/document list when "Check Uploads" is active
- Shows list of all documents currently being processed
- Each document item displays:
  - Document filename
  - Progress bar with three milestones: Uploading → Classification → Indexing
  - Current milestone highlighted/active
  - Percentage or status for current step
- Real-time updates via polling (every 1-2 seconds)
- Documents automatically removed from list when complete

#### 4. Duplicate Detection in Progress View
- When duplicate is detected during classification:
  - Progress stops at "Classification" milestone
  - Warning banner appears below progress bar
  - Shows existing document information (name, uploader, date)
  - "Replace & Index" button appears next to the document
  - User can click "Replace & Index" to proceed with replacement
  - After replacement, indexing milestone activates and continues

#### 5. Milestone Progress Indicators
- Three clear milestones displayed as steps or progress segments:
  1. **Uploading**: File upload to server (0-33%)
  2. **Classification**: LLM classification and duplicate check (33-66%)
  3. **Indexing**: Embedding generation and storage (66-100%)
- Visual indicators:
  - Completed milestones: Green checkmark or filled segment
  - Active milestone: Highlighted with animation
  - Pending milestones: Grayed out
- Progress bar shows overall completion percentage

#### 6. Background Processing
- All upload, classification, and indexing happens asynchronously
- No blocking UI - user can continue working while uploads process
- Real-time status updates via API polling
- Automatic progression through milestones when no duplicates
- User intervention only required for duplicate documents

## Phase 3: Company Document Management UI/UX

### User Flow
1. User views **shared** list of companies with uploaded documents (all users see the same list)
2. User selects a company
3. System displays document list with metadata (including attribution showing who uploaded each document)
4. Any user can trigger financial analysis on unprocessed documents (attribution tracked to the user who initiated it)

### UI Components Needed

#### 1. Company List View
- Layout: Vertical list view in left panel
- Company items: Each row shows:
  - Company name (primary)
  - Ticker symbol (secondary, if available)
  - Document count badge
  - Last updated timestamp
- Search functionality: Search bar at top of list (filter by company name or ticker)
- Sorting options: Alphabetical (A-Z, Z-A), by document count, by last updated
- Click to expand/navigate to company detail
- Show empty state if no companies exist
- Pagination or infinite scroll if list is long

#### 2. Company Detail Page
- Header: Company name, ticker symbol, and key stats (total documents, analyses)
- Document list: Vertical list in left panel when company is selected
- Document card/row design:
  - Document filename (truncate if long)
  - Document type badge
  - Upload date and time
  - Uploader attribution: User name with avatar/initials
  - Status indicators (indexed, processing, error)
  - Quick actions (view, delete if user is uploader)
- Attribution display:
  - User avatar (circular, with initials if no picture)
  - User name next to "Uploaded by [Name]"
  - Timestamp in relative format (e.g., "2 hours ago")
- Hover state: Highlight row and show additional actions
- Click document to view in right panel

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

