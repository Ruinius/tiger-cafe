# Frontend Refactoring Plan 2.0

## Problem Statement
The current frontend architecture has drifted from the initial design.
1.  **Mismatched Structure**: The file system (`components/documents`, `components/analysis`) categorizes by domain, but the application structure is monolithic (`LeftPanel`, `RightPanel`), leading to cognitive dissonance.
2.  **Monolithic Components**: `LeftPanel.jsx` (~1200 lines) and `RightPanel.jsx` (~1600 lines) act as massive controllers handling data fetching, complex state, event listeners, and UI rendering.
3.  **Loose Ends**: There are unresolved visual bugs (alignment), "fake" static methods, and scattered utilities that need consolidation.

## Goals
1.  **Align File Structure**: Reorganize codebase to match the **User Journey (Views)** rather than arbitrary domains or static panels.
2.  **De-bloat Components**: Extract logic into custom hooks and sub-components. Target < 200 lines for main containers.
3.  **Encapsulation**: Ensure each **View** manages its own internal concerns (e.g., PDF state in Document View, Analysis state in Company View) without leaking details.

## Target UI Layout & Flow (User Journey)
The application application state is defined by the user's depth of navigation. Instead of fixed "Left/Right" monoliths, the app will render distinct **Views** that define the content of both panels simultaneously.

### State 1: Global Dashboard (Home)
*   **Trigger**: Initial Load / "Companies" Breadcrumb.
*   **Left Panel**: `CompanyList`
    *   Searchable list of all companies.
    *   "Add Document" entry point.
    *   "Check Uploads" entry point.
*   **Right Panel**: `WelcomeView`
    *   Global recent activity.
    *   System-wide stats.
    *   Empty state/Introduction.

### State 2: Company Overview
*   **Trigger**: User selects a Company.
*   **Left Panel**: `DocumentList`
    *   Breadcrumb: `< Companies`.
    *   List of documents belonging to the selected company.
*   **Right Panel**: `CompanyAnalysisView`
    *   Aggregated metrics for the company.
    *   Financial Model / Valuation summary (DCF).
    *   Cross-document trends.

### State 3: Document Analysis
*   **Trigger**: User selects a Document.
*   **Left Panel**: `PdfViewer`
    *   Breadcrumb: `< [Company Name]`.
    *   Collapsible PDF view.
    *   Document Metadata (Status, Type).
*   **Right Panel**: `DocumentExtractionView`
    *   Tabbed interface for Extractions (Balance Sheet, Income Statement) vs Analysis (Calculations).
    *   Specific validation controls for the active document.

### Global Interactions (Modals)
*   **Upload Modal**:
    *   **Trigger**: "Add Document" button (available in Company List & Document List).
    *   **Behavior**: Modal dialog for file selection.
*   **Upload Progress Modal**:
    *   **Trigger**: "Check Uploads" button (replaces "Add Document" when uploads are active).
    *   **Behavior**: Modal dialog showing progress of current uploads.
    *   **Note**: Previously an overlay, now a distinct modal for cleaner separation.

### Implications for Refactoring
This architecture replaces the monolithic `LeftPanel` and `RightPanel` components with a specialized **View Orchestrator** in `Dashboard.jsx`.
*   `Dashboard.jsx` holds the `viewState`: `{ type: 'GLOBAL' | 'COMPANY' | 'DOCUMENT', data: ... }`
*   It renders `<SplitScreen left={<ComponentX />} right={<ComponentY />} />` based on the state.
*   Modals are rendered at the `Dashboard` level, outside the SplitScreen.



## Scope of Refactor
This refactor targets the entire frontend component layer. The following files will be **moved, renamed, or deleted**:

**Containers (To Be Deleted)**:
*   `src/components/LeftPanel.jsx` (and `.css`)
*   `src/components/RightPanel.jsx` (and `.css`)

**Analysis Components (To Be Moved)**:
*   `src/components/analysis/CompanyAnalysisView.jsx`
*   `src/components/analysis/DocumentExtractionView.jsx`
*   `src/components/analysis/FinancialModel.jsx` (and `.css`)

**Document Components (To Be Moved)**:
*   `src/components/documents/PdfViewer.jsx`
*   `src/components/documents/UploadProgress.jsx`

**Navigation Components (To Be Moved)**:
*   `src/components/navigation/CompanyList.jsx`
*   `src/components/navigation/DocumentList.jsx`

**Dashboard Components (To Be Moved)**:
*   `src/components/dashboard/WelcomeView.jsx`

**Common/Shared Components (To Be Moved)**:
*   `src/components/common/LineItemTable.jsx`
*   `src/components/common/OrganicGrowthTable.jsx`
*   `src/components/common/OtherAssetsTable.jsx`
*   `src/components/common/OtherLiabilitiesTable.jsx`
*   `src/components/common/SharesOutstandingTable.jsx`

**Layout Components (To Be Moved)**:
*   `src/components/Header.jsx` (and `.css`)
*   `src/components/SplitScreen.jsx` (and `.css`)
*   `src/components/UploadModal.jsx` (and `.css`)

This covers 100% of the active UI code.

## Execution Steps

### Phase 1: Structural Reorganization
Move all existing components into the new View-Based directory structure. This ensures every file has a clear place in the new architecture.

#### 1. Layout (`src/components/layout/`)
*   `Header.jsx` & `.css` → (Move from root)
*   `SplitScreen.jsx` & `.css` → (Move from root)

#### 2. Global View (`src/components/views/global/`)
*   `WelcomeView.jsx` → (Move from `dashboard/`)
*   `CompanyList.jsx` → (Move from `navigation/`)

#### 3. Company View (`src/components/views/company/`)
*   `CompanyAnalysisView.jsx` → (Move from `analysis/`)
*   `FinancialModel.jsx` & `.css` → (Move from `analysis/`)
*   `DocumentList.jsx` → (Move from `navigation/`)

#### 4. Document View (`src/components/views/document/`)
*   `DocumentExtractionView.jsx` → (Move from `analysis/`)
*   `PdfViewer.jsx` → (Move from `documents/`)

#### 5. Modals (`src/components/modals/`)
*   `UploadModal.jsx` & `.css` → (Move from root)
*   `UploadProgressModal.jsx` → (Rename & Move `documents/UploadProgress.jsx`)

#### 6. Shared (`src/components/shared/`)
*   `LineItemTable.jsx` & others → (Move all files from `common/` to `shared/tables/`)

#### 7. Cleanup
*   Delete empty source folders: `analysis/`, `dashboard/`, `documents/`, `navigation/`, `common/`.
*   Delete monolithic `LeftPanel.jsx` and `RightPanel.jsx` (after extracting logic in Phase 2/3).


### Phase 2: Logic Extraction (Hooks)
Deconstruct the monolithic logic into reusable custom hooks. ensuring the new Views can function independently.

1.  **`useDashboardData`**:
    *   Encapsulate `loadCompanies` and global polling.
2.  **`useDocumentData`**:
    *   Encapsulate `loadCompanyDocuments`, `fetchLatestStatus`, and document-specific polling.
3.  **`usePdfViewer`**:
    *   Encapsulate PDF state: `toggleChunk`, `expandAll`, `collapseAll`, `onHighlight`.
4.  **`useUploadManager`**:
    *   Encapsulate `handleUploadSuccess`, `handleReplaceAndIndex`, `uploadingDocuments` state.
5.  **`useAnalysisEvents`**:
    *   Encapsulate event listeners like `financialStatementsProcessingComplete` and `handleReloadCalculations`.
6.  **`useFormatting`**:
    *   Extract `formatNumber`, `formatPercent`, `formatDecimal` to `src/utils/formatting.js`.

### Phase 3: View Component Implementation
Refactor/Create the new View components to consume the hooks directly, removing dependency on props passed from a parent container.

1.  **Global Views**: `CompanyList` (uses `useDashboardData`), `WelcomeView`.
2.  **Company Views**: `DocumentList` (uses `useDocumentData`), `CompanyAnalysisView`.
3.  **Document Views**: `PdfViewer` (uses `usePdfViewer`), `DocumentExtractionView`.

### Phase 4: Dashboard Orchestration
Rewrite `Dashboard.jsx` to act as the **View Orchestrator**.

1.  **State Management**: Implement `viewState` (`GLOBAL`, `COMPANY`, `DOCUMENT`).
2.  **Routing Logic**: Render `SplitScreen` with the correct Left/Right components based on `viewState`.
3.  **Modal Management**: Mount `UploadModal` and `UploadProgressModal` at this level, controlled by global state or context.

### Phase 5: Cleanup & Polish
1.  **Delete** `LeftPanel.jsx` and `RightPanel.jsx`.
2.  **Visual Alignment**: Fix "Document" heading and buttons alignment in `PdfViewer` / `DocumentList`.
3.  **Polling Verification**: Ensure `fetchLatestStatus` and `useDashboardData` polling are efficient and don't leak.

## Success Criteria
*   `LeftPanel.jsx` and `RightPanel.jsx` **cease to exist**.
*   `Dashboard.jsx` is the single source of truth for View State.
*   Directory structure matches the UI Views (`src/components/views/...`).
*   All business logic is encapsulated in `src/hooks/`.