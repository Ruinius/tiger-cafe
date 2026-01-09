# Frontend Refactor Plan 4.0

**Status**: � **IN EXECUTION**
**Focus**: Technical Debt Clean-up & Modularization
**Based On**: [`docs/PRODUCT_SPECS.md`](./PRODUCT_SPECS.md)

---

## 1. Objective

The goal of Refactor Plan 4.0 is to eliminate critical technical debt identified in the frontend codebase. While the architecture (User Journey/View-Based State) is solid, the implementation of specific views and hooks suffers from monolithic design and lack of separation of concerns.

This refactor will **not** change user-facing features but will significantly improve maintainability, verify correctness, and enable easier testing.

## 2. High Priority Targets

### Target A: Decompose `DocumentExtractionView.jsx`

**Current State**:
- Monolithic component (~1000+ lines).
- Renders all financial tables inline (Balance Sheet, Income Statement, Historical Calculations).
- Duplicate logic for table rendering and validation.
- Hard to test individual table logic.

**Refactor Strategy**:
Split `DocumentExtractionView` into atomic, reusable table components.

1.  **Create `components/tables/` directory** (if not exists).
3.  **Shared Component Strategy**:
    -   Extract `LineItemTable` to `components/tables/shared/LineItemTable.jsx`.
    -   **Refactor**: Remove `balanceSheet` and `incomeStatement` prop dependencies. The component should be "dumb" and accept explicit `currency`, `unit`, and `timePeriod` props.
    -   **Usage**: Wrapper components (`BalanceSheetTable`, `IncomeStatementTable`) will be responsible for resolving these values before passing them to `LineItemTable`.

4.  Extract table logic into individual components with reference to `DocumentExtractionView.jsx` source lines:

    **Group A: Wrappers for `LineItemTable`**
    -   `BalanceSheetTable.jsx`: Lines ~435-442
    -   `IncomeStatementTable.jsx`: Lines ~447-454
    -   `NonGaapTable.jsx`: Lines ~470-475
    -   `NonOperatingClassificationTable.jsx`: Lines ~492-499

    **Group B: Custom Table Implementations**
    -   `OrganicGrowthTable.jsx`: Lines ~460-466 & ~1314-1382 (Specific row logic)
    -   `SharesOutstandingTable.jsx`: Lines ~482-487 & ~1254-1312 (Specific error states)
    -   `InvestedCapitalTable.jsx`: Lines ~512-805 (Complex nested structure)
    -   `EBITATable.jsx`: Lines ~813-900 (Specific breakdown logic)
    -   `AdjustedTaxTable.jsx`: Lines ~903-1043 (Calculation rows)
    -   `NopatRoicTable.jsx`: Lines ~1047-1109 (Derived metrics)
    -   `SummaryTable.jsx`: Lines ~1112-1243 (Aggregated metrics)

5.  Each component should:
    -   Accept data as props.
    -   Handle its own specific display logic (row mapping, styling).
    -   Use shared CSS classes from `components.css`.
6.  Update `DocumentExtractionView` to be a lightweight composition layer.

### Target B: Decompose `useDocumentData.js`

**Current State**:
- "God Hook" (~320 lines).
- Manages: Document metadata fetching, Extraction status polling, Financial data fetching, Calculation results fetching.
- Violates Single Responsibility Principle.

**Refactor Strategy**:
Split into focused custom hooks.

1.  **`useDocumentMetadata.js`**:
    -   Fetches basic info (filename, upload date, status).
    -   Handles polling for indexing status (if needed).
2.  **`useExtractionData.js`**:
    -   Fetches specific financial statements (BS, IS).
    -   Handles validation status updates.
3.  **`useCalculationData.js`**:
    -   Fetches historical calculations and derived metrics.
4.  **`useDocumentData.js`** (Compose):
    -   Can remain as a wrapper that combines the above for backward compatibility, OR refactor consumers (`DocumentView`, `DocumentExtractionView`) to use specific hooks directly.

## 3. Medium Priority Targets

### Target C: Style Consolidation

**Current State**:
- `styles/components_temp.css` exists with unclear usage.
- Table styles are fragmented between `components.css` and `Document.css`.
- Inconsistent use of CSS variables defined in `index.css`.

**CSS File Audit & Action Plan**:

1.  **Global & Base Styles**:
    -   **`src/index.css`**: **KEEP & ENFORCE.** The Single Source of Truth for Design Tokens (Colors, Typography, Shadows). All other files must use `var(--variable)` from here.
    -   **`src/App.css`**: **KEEP.** Minimal application wrapper reset.
    -   **`src/styles/layout.css`**: **REFACTOR.** Ensure it *only* handles structural layout (Flexbox/Grid relationships) and strips out any "visual" styling (colors, fonts).

2.  **Shared Component Styles (The Design System)**:
    -   **`src/styles/components.css`**: **PROMOTE.** This becomes the home for the **Premium Table System**. Move generic table classes (`.balance-sheet-table`, `.col-name`, etc.) here from `Document.css`.
    -   **`src/styles/components_temp.css`**: **DELETE.** Remove completely after verifying no unique styles remain.

3.  **View-Specific Styles**:
    -   **`src/components/views/document/Document.css`**: **SHRINK.** Remove generic table styles. Keep only view-specific overrides (e.g., specific column widths, PDF viewer layout).
    -   **`src/components/views/company/FinancialModel.css`**: **AUDIT.** Standardize inputs to use `components.css` styles and `index.css` variables.

**Execution Steps**:
1.  **Promote & Rename Table Styles**:
    -   Move table CSS from `Document.css` to `styles/components.css`.
    -   **Rename Classes**:
        -   `.balance-sheet-table` -> `.financial-table` (Generic)
        -   `.balance-sheet-container` -> `.table-container`
        -   `.balance-sheet-header` -> `.table-header`
        -   `.balance-sheet-meta` -> `.table-meta`
    -   **Update Consumers**:
        -   `src/components/tables/*.jsx`
        -   `src/components/views/company/FinancialModel.jsx` (Uses `.balance-sheet-table` for DCF results)
2.  **Standardize Variables**: grep for hex codes and replace with `var(--...)`.
3.  **Clean Layout**: Remove visual styles from `layout.css`.
4.  **Delete Legacy**: Remove `styles/components_temp.css`.

**Note on Other Table-Like Structures**:
-   `.company-list` (Dashboard, Document List): Uses Flexbox, not `<table>`. Keep separate.
-   `.metadata-grid` (Document Info): Uses CSS Grid. Keep separate.
-   `.upload-progress-list` (Upload Modal): Uses Flexbox. Keep separate.

### Target D: API Layer Abstraction

**Current State**:
- Direct `axios` calls scattered throughout components and hooks.
- Inconsistent error handling and config usage.

**Refactor Strategy**:
1.  Create `services/api.js` (or `api/` directory).
2.  Define typed/standardized fetchers:
    -   `companyService.getAll()`
    -   `documentService.get(id)`
    -   `documentService.getExtraction(id, type)`
3.  Update hooks to use these services instead of raw axios calls.

## 4. Execution Plan

### Phase 1: Component Decomposition
- [x] Create `components/tables/`
- [x] Extract `BalanceSheetTable` & `IncomeStatementTable`
- [x] Extract `OrganicGrowthTable` & `SharesOutstandingTable`
- [x] Extract `InvestedCapitalTable`, `EBITATable`, `AdjustedTaxTable`
- [x] Extract `NopatRoicTable`, `SummaryTable`
- [x] Extract `NonGaapTable` & `NonOperatingClassificationTable`
- [x] Verify `DocumentExtractionView` functionality

### Phase 2: Hook Decomposition
- [x] Create `useFinancialStatementProgress` (replaces `useDocumentMetadata`)
- [x] Create `useFinancialStatements` (replaces `useExtractionData`)
- [x] Create `useHistoricalCalculations` (replaces `useCalculationData`)
- [x] Update `DocumentExtractionView` to use new hooks

### Phase 3: CSS Refactor
- [ ] **Standardize Variables**:
    - [ ] Audit `src/styles/*.css` for hardcoded hex values.
    - [ ] Replace with `var(--...)` from `index.css`.
- [ ] **Promote Table Styles**:
    - [ ] Move table styles from `Document.css` to `components.css`.
    - [ ] Rename generic classes (`.balance-sheet-table` -> `.financial-table`, etc.).
- [ ] **Update Consumers**:
    - [ ] Update `components/tables/*.jsx` to use new class names.
    - [ ] Update `FinancialModel.jsx` styling.
- [ ] **Cleanup**:
    - [ ] Clean `layout.css` (remove visuals).
    - [ ] Shrink `Document.css` (remove generics).

### Phase 4: Cleanup & Testing
- [ ] **Audit** and Delete `styles/components_temp.css`
- [x] Add unit tests for new Table components
- [ ] Add unit tests for new Hooks
- [ ] **Manual Verification**:
    - [ ] Run full application smoke test.
    - [ ] Verify dark mode consistency.

## 5. Definition of Done

- `DocumentExtractionView.jsx` is under 200 lines of code.
- `useDocumentData.js` is decomposed or significantly simplified.
- All new components have basic unit tests.
- No user-facing regressions (verified via smoke tests).
- `components_temp.css` is deleted.
