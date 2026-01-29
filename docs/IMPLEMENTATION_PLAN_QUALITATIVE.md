# Implementation Plan: Qualitative Economic Moat & Future Growth Assessment

This plan outlines the steps to implement the LLM-based qualitative assessment feature, integrating it into the Company Analysis view and linking it to Financial Assumptions.

## 1. Backend Implementation

### 1.1. Data Models
Create a new SQLAlchemy model `QualitativeAssessment` in `app/models/qualitative_assessment.py`.

**Fields:**
- `id`: String (PK)
- `company_id`: String (FK to Company)
- `economic_moat_label`: String (Wide, Narrow, None)
- `economic_moat_rationale`: Text
- `near_term_growth_label`: String (Faster, Steady, Slower)
- `near_term_growth_rationale`: Text
- `updated_at`: DateTime (Tracks when the assessment was last performed/updated)

### 1.2. Schemas
Create Pydantic schemas in `app/schemas/qualitative_assessment.py` for API validation and serialization.

### 1.3. Agent Layer (`agents/qualitative_extractor.py`)
Create a new agent module to handle the LLM interaction.

**Responsibilities:**
- `extract_qualitative_assessment(ticker: str, company_name: str)`:
    - Construct a prompt asking for the 3 key pillars (Moat, Growth, Predictability) based on the LLM's **internal knowledge**.
    - **Do NOT** rely on RAG or fetched document text.
    - Return structured JSON with labels and rationales.

### 1.4. Service Layer (`app/services/qualitative_service.py`)
Create a service to orchestrate the workflow.

**Functions:**
- `run_qualitative_assessment(company_id, db)`:
    1.  Fetch Company details (Name, Ticker).
    2.  Call `extract_qualitative_assessment` agent (passing ticker/name).
    3.  Upsert `QualitativeAssessment` record.
    4.  Commit assessment changes.

### 1.5. Refactor Assumption Logic (`app/services/company_service.py`)

Move the complex logic from `app/routers/companies.py` into `app/services/company_service.py`.

**Refactoring Steps:**
1.  **Extract Logic**: Move the logic for generating default assumptions from `get_financial_assumptions` into a new function `get_or_create_assumptions(db, company_id, current_user)` in `company_service.py`.
    - This includes:
        - Fetching/Calculating Beta (Blume's).
        - Fetching Market Cap & Share Price.
        - Calculating Cost of Debt & Weight of Equity.
        - Calculating L4Q averages for default rates (Growth, Margin, Tax, etc.).
2.  **Integrate Qualitative Overrides**: Inside this service function, apply the qualitative assessment logic:
    - Query `QualitativeAssessment`.
    - **Terminal Growth**: Wide -> 4.0%, Narrow -> 3.5%, Else -> 3.0%.
    - **Stage 1 Growth**: Adjust L4Q base by +2.0% (Faster), -2.0% (Slower), or 0% (Steady).
3.  **Simplify Router**: Update `app/routers/companies.py` to simply call `company_service.get_or_create_assumptions`.

### 1.6. Router Layer (`app/routers/qualitative.py`)
Create new endpoints in `app/routers/qualitative.py` (and register in `main.py`).

- `GET /api/companies/{id}/qualitative-assessment`: Returns the current assessment.
- `POST /api/companies/{id}/qualitative-assessment/rerun`: 
    - Triggers the service to re-run analysis.
    - returns the new assessment.
    - *Note*: The frontend may choose to "Reset Assumptions" after this to apply the new defaults.

---

## 2. Frontend Implementation

### 2.1. Component `QualitativeAssessment.jsx`
Location: `frontend/src/components/views/company/QualitativeAssessment.jsx`

**Design Specs (adhering to UI_UX_DESIGN.md):**
- **Container**: Card style (Surface color, Border `1px solid var(--border)`, Radius `12px`, Shadow `sm`).
- **Layout**: Grid with 3 columns (side-by-side boxes).
- **Cards**:
    - **Header**: Item Title (e.g., "Economic Moat").
    - **Label**: Badge/Pill (e.g., "WIDE" in Green/Gold, "NONE" in Grey).
    - **Body**: Rationale text (`text-secondary`, `0.9rem`).
- **Actions**: "Re-run Assessment" button (Primary style).
    - *Behavior*: Sets loading state, calls API, refreshes data on completion.

### 2.2. Integration in `CompanyAnalysisView.jsx`
- Add `<QualitativeAssessment />` component section.
- Implement data fetching hook within the component (or pass down from view if preferred, but component-level fetching is cleaner for "Re-run" isolation).
- Handle 404s gracefully (show "No assessment available" or auto-trigger if first time behavior is desired).

---

## 3. Integration & Testing Plan

### 3.1. Database Migration
- Since we use `Base.metadata.create_all`, ensure the new model is imported in `app/models/__init__.py`.

### 3.2. Verification Steps
1.  **Extract**: Run "Re-run Assessment" on a company with a 10-K.
2.  **Verify UI**: Check if the 3 boxes appear with correct formatting.
3.  **Verify Assumptions**: Go to "Financial Model" tab and check if "Terminal Growth" and "Stage 1 Growth" have updated based on the assessment labels.

### 3.3. Error Handling
- **Missing Documents**: If no 10-K/10-Q exists, return 404 or specific error "No suitable document found for analysis".
- **LLM Failures**: Handle timeouts or bad JSON.
