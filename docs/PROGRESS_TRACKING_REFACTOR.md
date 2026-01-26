# Progress Tracking UI/UX Refactor Plan

## Section 1: NEW MILESTONES AND LOGS

This section details the proposed unified 12-step milestone structure, including detailed retries and error reasons.

### Proposed Milestones
1.  **`UPLOAD`** (`uploading`) - `app/routers/documents.py`
2.  **`CLASSIFICATION`** (`classifying`) - `app/services/document_processing.py`
3.  **`INDEX`** (`indexing`) - `app/services/document_processing.py`
4.  **`BALANCE_SHEET`** (`balance_sheet`) - `app/services/extraction_orchestrator.py`
5.  **`INCOME_STATEMENT`** (`income_statement`) - `app/services/extraction_orchestrator.py`
6.  **`SHARES_OUTSTANDING`** (`shares_outstanding`) - `app/services/extraction_orchestrator.py` (Agents: `agents/shares_outstanding_extractor.py`)
7.  **`ORGANIC_GROWTH`** (`organic_growth`) - `app/services/extraction_orchestrator.py` (Agents: `agents/organic_growth_extractor.py`)
8.  **`GAAP_RECONCILIATION`** (`gaap_reconciliation`) - `app/services/extraction_orchestrator.py` (Agents: `agents/gaap_reconciliation_extractor.py`)
9.  **`AMORTIZATION`** (`amortization`) - `app/services/extraction_orchestrator.py` (Agents: `agents/amortization_extractor.py`)
10. **`OTHER_ASSETS`** (`other_assets`) - `app/services/extraction_orchestrator.py` (Agents: `agents/other_assets_extractor.py`)
11. **`OTHER_LIABILITIES`** (`other_liabilities`) - `app/services/extraction_orchestrator.py` (Agents: `agents/other_liabilities_extractor.py`)
12. **`CLASSIFYING_NON_OPERATING_ITEMS`** (`classifying_non_operating_items`) - `app/services/extraction_orchestrator.py` (Agents: `agents/non_operating_classifier.py`)
13. **`CALCULATE_VALUE_METRICS`** (`calculate_value_metrics`) - `app/routers/historical_calculations.py`
14. **`UPDATE_HISTORICAL_DATA`** (`update_historical_data`) - `app/routers/companies.py`
15. **`UPDATE_ASSUMPTIONS`** (`update_assumptions`) - `app/routers/companies.py`
16. **`CALCULATE_INTRINSIC_VALUE`** (`calculate_intrinsic_value`) - `app/routers/companies.py`

### Statuses
*   `PENDING`
*   `IN_PROGRESS`
*   `COMPLETED`
*   `ERROR`
*   `WARNING` (New status for allowable missing data like optional tables)


## Section 2: CHECK UPDATES UI

### 2.1 Visual Layout: "The Mission Control Pattern"
*   **Structure**: Uses the `SplitScreen.jsx` component within `Dashboard.jsx`, rendering two distinct view files: `MissionControlDashboard.jsx` (Left) and `MissionControlLog.jsx` (Right).
*   **Default Ratio**: Fixed at `0.35` (35% Left / 65% Right) to accommodate the 16-milestone grid.
*   **Background**: Adheres to `UI_UX_DESIGN.md` (Surface color: `#FFFFFF` / `#1B1E24`). 
*   **Panel Consistency**: Both files use `.panel-content` and `.panel-header` from `layout.css`.
*   **Header Integration**: metadata (SSE health, doc count) and "Mission Control" branding displayed in the `.panel-header`.

### 2.2 Preserved Navigation & Breadcrumbs
*   **Breadcrumb Preservation**: The current breadcrumb structure (`Companies › Check Updates`) will be maintained within the split-pane header or the Left Panel header to ensure a consistent navigation path.
*   **Navigation Logic**: The `onBack` prop will be preserved and wired to the breadcrumb's "Companies" link, ensuring the user can exit the "Mission Control" view exactly as they do currently.
*   **Entry Point**: The existing trigger for the `CheckUpdatesView` (typically from the `AddDocumentButton` or Header) remains unchanged.

### 2.3 Left Panel: MissionControlDashboard (35%)
*   **Document Cards**: Styling follows `components.css` `.info-section`. Includes a "Focused" state (subtle neon-blue border) indicating which document is currently streaming to the Right Panel.
*   **The 16-Milestone Matrix**: 4x4 grid of tiles displaying the unified 12-step (expanded to 16) extraction flow.
    *   **Colors**: Tiles use opacity-based variants of standard tokens from `index.css`:
        *   `--success` (Emerald) for completed.
        *   `--info` (Blue) for in-progress.
        *   `--error` (Red) for failures.
    *   **Tooltips**: Reuses `.tooltip-container` and `.tooltip-text` from `components.css`.
*   **Interaction**: Clicking a card updates the `focusedDocumentId` state, immediately switching the Intelligence Stream to that document’s history.
*   **Global Progress Bar**: A custom linear progress bar using `--primary` with a CSS `box-shadow` glow representing completion weight.

### 2.4 Right Panel: MissionControlLog (65%)
*   **Interface**: Dark-mode primary background (`--bg-primary`). Shows logs for the `focusedDocumentId`.
*   **Chatbot Aesthetic**:
    *   **System Action**: Uses `--text-secondary` and `SF Mono` for a terminal-like feel.
    *   **AI Reasoning**: Bubbles use the Indigo-Purple gradient accentuating the primary theme. Font is `Inter` (Regular).
*   **Markdown Support**: Full rendering for snapshots, tables (Gold Standard), and emphasized keys.
*   **Sticky Scroll**: Standard implementation using `useRef` to follow the "drip" of incoming messages.

### 2.5 Technical Data Flow & SSE
*   **SSE Schema Update**: Includes `source` (`system`|`ai`) and `metadata`.
*   **Smooth Stream Accumulator**: 
    *   Stored in `UploadContext.js` as a persistent `Map`.
    *   **New**: Implementation of a 1-second "Drip Buffer". Incoming SSE events are queued and released to the state at a steady pace to prevent UI jitter and allow users to read AI reasoning.
*   **Persistency**: Log history survives view toggling between "Companies" and "Check Updates".

### 2.6 Aesthetic Tokens (Sync with index.css)
*   `--color-system-log`: `var(--text-secondary)`
*   `--color-ai-bubble-gradient`: `linear-gradient(135deg, #6366f1 0%, #a855f7 100%)`
*   `--color-milestone-success`: `var(--success)`
*   `--color-milestone-running`: `var(--info)` with `pulse` animation (defined in `components.css`).



## Section 3: IMPLEMENTATION PLAN

### Phase 1: Foundation & State (Data Layer)
1.  **Update `UploadContext.js`**:
    *   Introduce `processingLogs` state (a `Map` keyed by `documentId`).
    *   **Smooth Stream Buffer**: Implement a queue for incoming SSE messages. Instead of updating the state instantly, use a "drip" mechanism (e.g., `setInterval` or a recursive `setTimeout`) that processes one message from the queue every 800ms - 1200ms.
    *   **Why**: This ensures that even if the backend emits 10 logs in a split second, the UI "unfolds" them at a readable, cinematic pace, matching the "Tiger is thinking" aesthetic.
    *   Update the SSE listener to detect the new `source` field (`system` vs `ai`).
    *   Expose both the `processingLogs` and the `isStreaming` status to context consumers.

### Phase 2: Structural Refactor (Layout Layer)
1.  **Refactor `CheckUpdatesView.jsx` into the "Mission Control" Pattern**:
    *   Split the logic into two new components: `f:\AIML projects\tiger-cafe\frontend\src\components\views\global\MissionControlDashboard.jsx` (Left) and `f:\AIML projects\tiger-cafe\frontend\src\components\views\global\MissionControlLog.jsx` (Right).
    *   This mirrors the `DocumentView` / `DocumentExtractionView` separation found in `f:\AIML projects\tiger-cafe\frontend\src\components\views\document/`.
2.  **Update `f:\AIML projects\tiger-cafe\frontend\src\pages\Dashboard.jsx`**:
    *   Update `DEFAULT_RATIOS` for `CHECK_UPDATES` from `1.0` to `0.35`.
    *   Update the `CHECK_UPDATES` case in the switch statement to render `MissionControlDashboard` (Left) and `MissionControlLog` (Right) separately.
    *   Introduce a local `focusedDocumentId` state in `Dashboard.jsx` (or handle within Mission Control components) to coordinate which document's logs are visible in the Right Panel.
3.  **Implement Panel Consistency**:
    *   Both panels must use `.panel-content` and `.panel-header` from `layout.css`.
    *   `MissionControlDashboard` (Left) will host the breadcrumb: `Companies › Check Updates`.
    *   Breadcrumb must use the standard `.breadcrumb` and `.breadcrumb-link` classes to match `DocumentView.jsx`.

### Phase 3: Component Development (Milestone Matrix)
1.  **Develop `MissionControlDashboard.jsx`**:
    *   Implement the selection logic: Clicking a document card sets the `focusedDocumentId`.
    *   Display a distinct "active" state for the focused card.
    *   Render the 16-Milestone Matrix (4x4) using compact CSS grid.
    *   Integrate tooltips and the global progress bar as detailed in Section 2.
2.  **Develop `MissionControlLog.jsx`**:
    *   Accepts `focusedDocumentId` as a prop.
    *   Filters the `processingLogs` from `UploadContext` to show only messages for the focused document.
    *   Implement the chat-style stream with color-coded bubbles (`system` slate vs `ai` purple-gradient).
    *   Add the "Tiger is thinking..." animation and sticky auto-scroll logic.

### Phase 4: UX & Polish (Interactions)
1.  **Sticky Scrolling**: Use `useRef` to ensure the chat automatically follows the latest logs unless the user manually scrolls up.
2.  **Breadcrumb Wiring**: Ensure "Companies" breadcrumb correctly triggers `onBack`.
3.  **Session Persistence**: Verify that logs remain available when the user toggles between the Dashboard and Mission Control during an active session.

### Phase 5: Verification (Testing)
1.  **Manual Verification**: Perform a batch upload and trigger a full extraction re-run.
2.  **Log Validation**: Confirm that "App Activities" and "AI Thoughts" are correctly categorized and colored.
3.  **Responsiveness**: Test the `SplitScreen` divider to ensure the 4x4 grid handles narrower widths gracefully.