# Frontend Refactor Plan

## 1. Problem Statement
The current frontend architecture relies heavily on two monolithic components: `LeftPanel.jsx` and `RightPanel.jsx`. These components have become "God Objects," creating several issues:
- **State Complexity:** They manage unrelated states (uploads, navigation, viewing, analysis, polling) in single locations.
- **Performance Issues:** Minor updates (e.g., upload progress) trigger re-renders of the entire panel hierarchy.
- **Stability Bugs:** The "infinite polling" bug is a direct result of unstable callback references passed between these monolithic components and `Dashboard.jsx`.
- **Maintainability:** The files are becoming too large to effectively navigate and edit.

## 2. Target Architecture
The goal is to decompose the application into a domain-driven component hierarchy, separating **Navigation**, **Content Viewing**, and **Background Processes**.

### Core Concepts
1.  **Smart vs. Dumb Components:** Move logic out of the UI presentation layers.
2.  **Context for Global State:** Use React Context for state that persists across views (e.g., Upload Status, Auth).
3.  **Stable Layouts:** `Dashboard` should provide the layout, but specific panels should manage their own local logic.

## 3. Component Decomposition

### A. Left Panel (Navigation & Inputs)
Current: `LeftPanel.jsx` (Handles everything)
Proposed Breakdown:
1.  **`components/navigation/CompanyList.jsx`**:
    - Displays list of companies.
    - Handles "Select Company" events.
2.  **`components/navigation/DocumentList.jsx`**:
    - Displays list of documents for a selected company.
    - Handles "Select Document" events.
3.  **`components/documents/UploadManager.jsx`** (or `UploadStatus.jsx`):
    - Independent component to display upload progress.
    - Should likely rely on a global `UploadContext` rather than local polling state.
4.  **`components/documents/PdfViewer.jsx`**:
    - Encapsulates PDF rendering logic.
    - Manages its own blob URL creation/cleanup.

### B. Right Panel (Content & Analysis)
Current: `RightPanel.jsx` (Handles extracts, financial model, historicals)
Proposed Breakdown:
1.  **`components/dashboard/WelcomeView.jsx`**:
    - The "Latest Analyses" view shown when nothing is selected.
    - Can be a true dashboard component.
2.  **`components/analysis/CompanyAnalysisView.jsx`**:
    - The top-level container for Company operations.
    - Shows `HistoricalDataTables` and `FinancialModel`.
3.  **`components/analysis/DocumentExtractionView.jsx`**:
    - Shows the specific extracted data (Balance Sheet, Income Statement) for a single document.
    - Reuses generic table components.
4.  **`components/financials/FinancialModel.jsx`**:
    - existing component, but cleanly separated.

### C. State Management (The "Glue")
1.  **`contexts/UploadContext.js`**:
    - **Crucial**: Moves upload polling and state OUT of the UI components.
    - The `LeftPanel` will just subscribe to this context to show a progress bar.
    - This eliminates the "LeftPanel re-render kills polling" loop.
2.  **`Dashboard.jsx` Clean-up**:
    - Should simply manage the High-Level Selection State (`selectedCompanyId`, `selectedDocumentId`).
    - **Must** use `useCallback` for all handlers passed down to children to prevent unnecessary re-renders.

## 4. Implementation phases

### Phase 1: Stabilization (Immediate)
*Goal: Stop the "freaking out" behavior without full rewrite.*
1.  Wrap `handleBack`, `handleCompanySelect`, `handleDocumentSelect` in `useCallback` in `Dashboard.jsx`.
2.  Ensure `useEffect` dependencies in `LeftPanel` are exhaustive and correct.
3.  Verify polling stops when it should.

### Phase 2: Context Extraction
*Goal: decouple background processes from UI.*
1.  Create `UploadContext`.
2.  Move `loadUploadProgress` and polling logic into the Context Provider.
3.  Wrap the app (or Dashboard) in `UploadProvider`.
4.  Update `LeftPanel` to consume `useUpload()` instead of managing polling itself.

### Phase 3: Component Split - Left Panel
*Goal: Modularize navigation.*
1.  Extract `PdfViewer`.
2.  Extract `CompanyList` and `DocumentList`.
3.  Refactor `LeftPanel` to be a composition of these smaller components.

### Phase 4: Component Split - Right Panel
*Goal: Modularize analysis views.*
1.  Extract `DocumentExtractionView`.
2.  Extract `CompanyAnalysisView`.
3.  Refactor `RightPanel` to switch between these views based on `selectedDocument` / `selectedCompany` props.

## 5. Directory Structure Target
```
frontend/src/
  components/
    common/              # Generic UI (Tables, Badges, Loaders)
    navigation/          # Lists, Sidebars
    documents/           # PDF Viewer, Upload controls
    analysis/            # Financial tables, Models
    dashboard/           # Top level views
  contexts/
    UploadContext.js
    AuthContext.js
  pages/
    Dashboard.jsx
```
