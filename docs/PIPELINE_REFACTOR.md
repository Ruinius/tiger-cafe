# PIPELINE REFACTOR

## Section 1: Current Process Flow

### Overview
The current pipeline processes financial documents through a multi-stage extraction and classification workflow using multiple specialized LLM agents. The process is orchestrated by a queue-based system that handles documents sequentially.

### Detailed Flow (Document Upload → Financial Model Assembly)

#### **Stage 1: Document Upload & Initial Processing**
1. **User uploads PDF document** (`/api/documents/upload`)
   - File saved to `UPLOAD_DIR`
   - Document record created with `PENDING` status
   - Document added to processing queue

2. **Queue picks up document** (`DocumentQueue._process_document_end_to_end`)
   - Status: `PENDING` → `CLASSIFYING`

#### **Stage 2: Classification & Indexing**
3. **Document Classification** (`agents/document_classifier.py`)
   - **Agent**: `classify_document()`
   - **LLM Task**: Extract document metadata from first 10,000 characters
   - **Outputs**:
     - `document_type` (earnings_announcement, quarterly_filing, annual_filing, etc.)
     - `time_period` (e.g., "Q3 2024")
     - `period_end_date` (e.g., "2024-09-30")
     - `company_name`
     - `ticker`
     - `confidence` level
   - **Temperature**: 0.0 (deterministic)

4. **Document Indexing** (if earnings announcement)
   - Full text extraction from PDF
   - Chunk document into sections
   - Generate embeddings for semantic search
   - Store in vector database
   - Status: `CLASSIFYING` → `INDEXED`

5. **Non-earnings documents terminate here**
   - Status: `INDEXED` → `CLASSIFIED`
   - End of pipeline

#### **Stage 3: Balance Sheet Extraction** (Earnings Announcements Only)
6. **Balance Sheet Section Location** (`agents/balance_sheet_extractor.py`)
   - **Agent**: `find_top_numeric_chunks()`
   - **Process**:
     - Scan all document chunks and count numeric values in each
     - Rank chunks by numeric density (highest to lowest)
     - Retrieve top 5 chunks with most numbers
     - For each candidate chunk (in order of numeric density):
       - Extract chunk text with 1 page padding before/after
       - **LLM Task**: Validate completeness with `check_balance_sheet_completeness_llm()`
       - If complete, proceed to extraction
       - If incomplete, try next candidate chunk
     - Retry with up to 5 candidate chunks until a complete balance sheet is found

7. **Balance Sheet Extraction** 
   - **Agent**: `extract_balance_sheet_llm()`
   - **LLM Task**: Extract line items exactly as they appear
   - **Outputs per line item**:
     - `line_name` (original name from document)
     - `line_value` (numerical value)
     - `unit` (ones, thousands, millions, billions)
     - `category` (current_assets, non_current_assets, current_liabilities, etc.)
   - **Temperature**: 0.0

8. **Balance Sheet Line Item Standardization**
   - **Agent**: `get_balance_sheet_llm_insights()`
   - **LLM Task**: Identify key line items and map to standardized names
   - **Standardized Names**:
     - Total Current Assets
     - Total Non-Current Assets
     - Total Assets
     - Total Current Liabilities
     - Total Non-Current Liabilities
     - Total Liabilities
     - Total Equity
     - Total Liabilities and Equity
   - **Format**: "Standardized Name (Original Name)"

9. **Balance Sheet Calculation Validation**
   - **Agent**: `validate_balance_sheet_calculations()`
   - **Process**: Verify that subtotals and totals match reported values
   - **Three-Step Retry Logic**:
     1. **Initial Validation**: Check if totals match sums of components
     2. **Time Period Filtering** (if validation fails):
        - **LLM Task**: Use `check_line_item_time_periods_balance_sheet()` to identify line items from wrong time periods
        - Remove mismatched items (e.g., prior year data mixed with current period)
        - Re-validate after removal
     3. **LLM Feedback Re-extraction** (if still invalid):
        - **LLM Task**: Call `extract_balance_sheet_llm_with_feedback()` with previous extraction and specific validation errors
        - LLM reviews errors and re-extracts with corrections
        - Final validation attempt

10. **Balance Sheet Operating Classification**
    - **Agent**: `classify_line_items_llm()`
    - **LLM Task**: Classify each line item as operating or non-operating
    - **Uses**: LLM with Authoritative_Lookup
    - **Outputs**: `is_operating` (true/false/null)

#### **Stage 4: Income Statement Extraction**
11. **Income Statement Section Location** (`agents/income_statement_extractor.py`)
    - **Agent**: `find_top_numeric_chunks()`
    - **Process**:
      - Same numeric density approach as balance sheet (scan all chunks, rank by number count)
      - Retrieve top 5 chunks with most numbers
      - For each candidate chunk (in order of numeric density):
        - Extract chunk text with 1 page padding before/after
        - **LLM Task**: Validate completeness with `check_income_statement_completeness_llm()`
        - If complete, proceed to extraction
        - If incomplete, try next candidate chunk
      - Retry with up to 5 candidate chunks until a complete income statement is found
    - **Note**: The legacy `find_income_statement_near_balance_sheet()` function exists but is not used in the main flow

12. **Income Statement Extraction**
    - **Agent**: `extract_income_statement_llm()`
    - **LLM Task**: Extract line items exactly as they appear
    - **Outputs per line item**:
      - `line_name` (original name)
      - `line_value` (numerical value)
      - `unit` (ones, thousands, millions, billions)
      - `category` (revenue, cost_of_revenue, operating_expense, etc.)
    - **Additional**: Extract prior year revenue for YoY comparison
    - **Temperature**: 0.0

13. **Income Statement Operating Classification** (Stage 1)
    - **Agent**: `classify_line_items_llm()`
    - **LLM Task**: Classify each line item as operating or non-operating, and expense vs revenue
    - **Uses**: LLM with Authoritative_Lookup
    - **Outputs**: 
      - `is_operating` (true/false/null)
      - `is_expense` (true/false/null)
    - **Note**: This happens immediately after extraction, before post-processing

14. **Income Statement Post-Processing** (Stage 2)
    - **Agent**: `post_process_income_statement_line_items()`
    - **Process**:
      - **LLM Task**: Use `get_income_statement_llm_insights()` to identify key line items
      - Standardize key line item names (format: "Standardized Name (Original Name)")
      - Detect cost format (positive vs negative)
      - Normalize costs to negative values
      - Validate calculations during normalization
    - **Standardized Names**:
      - Total Net Revenue
      - Cost of Revenue
      - Gross Profit
      - Operating Expenses
      - Operating Income
      - Pretax Income
      - Tax Expense
      - Net Income
    - **Three-Step Retry Logic** (if validation fails):
      1. **Initial Validation**: Check if calculations are correct (e.g., Revenue - Costs = Gross Profit)
      2. **Time Period Filtering**: Remove line items from wrong time periods, re-validate
      3. **LLM Feedback Re-extraction**: Re-extract with validation errors, re-classify, re-validate

#### **Stage 5: Additional Data Extraction**
16. **GAAP Reconciliation Extraction** (`agents/gaap_reconciliation_extractor.py`)
    - **Agent**: `extract_gaap_reconciliation()`
    - **LLM Task**: Extract GAAP to non-GAAP reconciliation table
    - **Process**:
      - Use embeddings to find reconciliation section
      - Extract line items (adjustments from operating income to EBITDA)
      - Validate that sum equals final line item
      - Classify items as operating/non-operating

17. **Organic Growth Extraction** (`agents/organic_growth_extractor.py`)
    - **Agent**: `extract_organic_growth()`
    - **LLM Task**: Identify acquisition impact on revenue
    - **Process**:
      - Search for acquisition-related text
      - Extract acquisition revenue impact
      - Calculate organic vs inorganic growth
    - **Outputs**:
      - `acquisition_flag` (true/false)
      - `acquisition_revenue_impact`
      - `simple_revenue_growth` (%)
      - `organic_revenue_growth` (%)

18. **Shares Outstanding Extraction** (`agents/shares_outstanding_extractor.py`)
    - **Agent**: `extract_shares_outstanding()`
    - **LLM Task**: Extract basic and diluted shares outstanding
    - **Process**:
      - Search for weighted average shares
      - Try multiple chunk ranks if not found
    - **Outputs**:
      - `basic_shares_outstanding`
      - `diluted_shares_outstanding`

19. **Other Assets Extraction** (`agents/other_assets_extractor.py`)
    - **Agent**: `extract_other_assets()`
    - **Process**: Extract detailed breakdown of "Other Current Assets" and "Other Non-Current Assets"
    - **Uses**: Balance sheet line items as query terms
    - **Document Types**: Quarterly filings and annual filings only (skipped for earnings announcements)

20. **Other Liabilities Extraction** (`agents/other_liabilities_extractor.py`)
    - **Agent**: `extract_other_liabilities()`
    - **Process**: Extract detailed breakdown of "Other Current Liabilities" and "Other Non-Current Liabilities"
    - **Uses**: Balance sheet line items as query terms
    - **Document Types**: Quarterly filings and annual filings only (skipped for earnings announcements)

21. **Amortization Extraction** (`agents/amortization_extractor.py` or `agents/gaap_reconciliation_extractor.py`)
    - **For Earnings Announcements**:
      - **Agent**: `extract_gaap_reconciliation()`
      - **LLM Task**: Extract GAAP to non-GAAP (EBITDA) reconciliation table
      - **Process**: Search for reconciliation section, extract adjustments from operating income to EBITDA
    - **For Quarterly/Annual Filings**:
      - **Agent**: `extract_amortization()`
      - **Process**: Search for D&A in cash flow statement or notes

#### **Stage 6: Non-Operating Classification**
22. **Non-Operating Item Categorization** (`agents/non_operating_classifier.py`)
    - **Agent**: `classify_non_operating_items()`
    - **LLM Task**: Categorize non-operating items into specific buckets
    - **Categories**:
      - cash
      - short_term_investments
      - operating_lease_related
      - other_financial_physical_assets
      - debt
      - other_financial_liabilities
      - deferred_tax_assets
      - deferred_tax_liabilities
      - common_equity
      - preferred_equity
      - minority_interest
      - goodwill_intangibles
      - unknown

#### **Stage 7: Financial Model Assembly**
23. **Historical Calculations** (`app/routers/historical_calculations.py`)
    - **Process**: Calculate derived financial metrics
    - **Calculations**:
      - Revenue YoY Growth
      - EBITA (Operating Income + Amortization)
      - EBITA Margin
      - Effective Tax Rate
      - Adjusted Tax Rate
      - NOPAT (Net Operating Profit After Tax)
      - Net Working Capital
      - Net Long Term Operating Assets
      - Invested Capital
      - Capital Turnover
      - ROIC (Return on Invested Capital)

24. **Financial Model Complete**
    - Status: `PROCESSING_COMPLETE`
    - All data available for DCF valuation and analysis

---

## Section 2: Simplified Flow with Tiger-Transformer

### Overview
The tiger-transformer model (https://huggingface.co/Ruinius/tiger-transformer) is a fine-tuned FINBERT model trained to standardize financial statement line items and classify their properties. This could replace multiple LLM agent steps with a single, fast, specialized model.

### Proposed Simplified Flow

#### **Stages 1-2: Document Upload & Classification** (Unchanged)
- Document upload
- Document classification (document type, time period, company)
- Document indexing

#### **Stage 3: Balance Sheet Extraction** (Simplified)
1. **Balance Sheet Section Location** (Unchanged)
   - Use 5 chunks with most numbers to find balance sheet section
   - Validate completeness

2. **Balance Sheet Line Item Extraction** (Slight change)
   - Extract line items with original names and values
   - Section classification (LLM prompt must output exact tokens: `current_assets`, `noncurrent_assets`, `current_liabilities`, `noncurrent_liabilities`, `stockholders_equity`)

3. **Balance Sheet Standardization & Classification** (**NEW: Single Tiger-Transformer Call**)
   - **Input**: List of line items in sequential order with:
     - Original line item names (preserve original casing/punctuation)
     - Context window (2 previous and 2 next line items)
     - Pre-processing to ensure section classification confirms with needed tag. If the name exists but is in the wrong format, fix with a few rules. If the name is missing or cannot be fixed, then use the classification before and after this line item. If a critical mass of labels are missing, exit with error.
     - Format: `[PREV_2] [PREV_1] [SECTION] [RAW_NAME] [NEXT_1] [NEXT_2]`
     - Example: `[<START>] [<START>] [current_assets] [Cash and cash equivalents] [Marketable securities] [Accounts receivable]`
   - **Tiger-Transformer Outputs**:
     - `standardized_name` (e.g., "cash_and_equivalents", "total_current_assets")
   - **Lookup table**:
     - Uses lookup tables (`bs_calculated_operating_mapping.csv`)
     - `is_calculated` (true/false) - whether this is a calculated total/subtotal (via lookup table)
     - `is_operating` (true/false) - operating vs non-operating classification (via lookup table)
   - **Replaces**:
     - ~~`get_balance_sheet_llm_insights()` - LLM call to identify key items~~
     - ~~`classify_line_items_llm()` - LLM call to classify operating/non-operating~~
   - **Benefits**:
     - Single model inference instead of 2 separate LLM calls
     - Faster (transformer inference ~100-500ms vs LLM generation ~5-15 seconds)
     - More consistent (trained on labeled data)
     - Context-aware standardization using surrounding line items

4. **Balance Sheet Validation**
   - Validate calculations using standardized names and `is_calculated` flag
   - Apply retry logic if validation fails (Time Period Filtering, LLM Feedback)

#### **Stage 4: Income Statement Extraction** (Simplified)
1. **Income Statement Section Location** (Unchanged)
   - Find income statement section
   - Validate completeness

2. **Income Statement Line Item Extraction**
   - Extract line items with original names and values

3. **Income Statement Standardization & Classification** (**NEW: Single Tiger-Transformer Call**)
   - **Input**: List of line items in sequential order with:
     - Original line item names (preserve original casing/punctuation)
     - Section classification (LLM prompt must output `income_statement` token)
     - Context window (2 previous and 2 next line items)
     - Format: `[PREV_2] [PREV_1] [SECTION] [RAW_NAME] [NEXT_1] [NEXT_2]`
     - Example: `[<START>] [<START>] [income_statement] [Total Net Revenue] [Cost of Revenue] [Gross Profit]`
   - **Tiger-Transformer Outputs**:
     - `standardized_name` (e.g., "total_net_revenue", "operating_income")
   - **Lookup table**:
     - Uses lookup tables (`is_calculated_operating_expense_mapping.csv`)
     - `is_calculated` (true/false) - whether this is a calculated total/subtotal (via lookup table)
     - `is_operating` (true/false) - operating vs non-operating (via lookup table)
     - `is_expense` (true/false) - expense vs revenue/income (via lookup table)
   - **Replaces**:
     - ~~`get_income_statement_llm_insights()` - LLM call to identify key items~~
     - ~~`classify_line_items_llm()` - LLM call to classify operating/non-operating and expense~~
   - **Benefits**:
     - Single model inference instead of 2 separate LLM calls
     - Faster and more consistent
     - Trained specifically on income statement patterns
     - Context-aware standardization using surrounding line items

4. **Income Statement Normalization & Validation**
   - **Normalization**: Enforce negative signs for items where `is_expense` is true (if positive, multiply by -1)
   - **Treating `is_expense`=null**: If most of `is_expense`=true line items are positive, then multiply `is_expense`=null line items by -1 otherwise, leave as is. This assumes `is_expense`=null are treated like expenses by default, but they could be income, which requires checking during validation.
   - **Validation**:
     - Validate calculations using standardized names and `is_calculated` flag
     - Compare the validation residual to the line_items where `is_expense`=null
     - If the residual can be explained by 1-2 `is_expense`=null line items flipping signs, then do it and pass validation
   - **Re-try logic**:
     - Apply retry logic if validation fails (Time Period Filtering, LLM Feedback)

#### **Stages 5-7: Additional Extraction & Assembly** (Unchanged)
- GAAP reconciliation extraction
- Organic growth extraction
- Shares outstanding extraction
- Other assets/liabilities extraction
- Amortization extraction
- Non-operating classification
- Historical calculations
- Financial model assembly

### Implementation Considerations

1. **Model Deployment**
   - **Development**: Load model locally using `transformers` (leveraging local GPU/CPU) for zero-latency testing
   - **Production**: Option to containerize as a microservice or use HuggingFace Inference API later
   - **Action**: Create a `TigerTransformerClient` class that loads the model from `../tiger-transformer/models`

2. **Training Data Updates**
   - Create a script where I can export a specific company's financial statements in the following format:
     - **File Name**: `{TICKER}_{BS|IS}_{PERIOD}.csv` (e.g., `ADBE_BS_Q42025.csv`)
     - **Columns**: `row_name`, `section`, `is_calculated`, `standardized_name`, `company`
   - This aligns with the existing `balance_sheet_clean_label` and `income_statement_clean_label` structure used for training.
   - The output folder can be data/tiger-transformer_add_data

---

## Section 3: Data Model Changes
To support the new standardized outputs from the `tiger-transformer`, the following schema updates are required:

### 1. Database Models (SQLAlchemy)

#### **Balance Sheet Line Items** (`app/models/balance_sheet.py`)
- **Table**: `balance_sheet_line_items`
- **New Columns**:
  - `standardized_name` (String, nullable=True): The standardized key from the transformer (e.g., `cash_and_equivalents`).
  - `is_calculated` (Boolean, nullable=True): Flag indicating if the value is a calculated total/subtotal.
- **Existing Field Usage**:
  - `line_category`: Will now strictly store the section token (e.g., `current_assets`, `stockholders_equity`) input to the transformer.

#### **Income Statement Line Items** (`app/models/income_statement.py`)
- **Table**: `income_statement_line_items`
- **New Columns**:
  - `standardized_name` (String, nullable=True): The standardized key from the transformer.
  - `is_calculated` (Boolean, nullable=True): Flag indicating if the value is a calculated total/subtotal.
  - `is_expense` (Boolean, nullable=True): Flag indicating if the item is an expense (used for sign normalization).
- **Existing Field Usage**:
  - `line_category`: Will store the section token (e.g., `income_statement`).

### 2. API Schemas (Pydantic)

#### **Balance Sheet Schemas** (`app/schemas/balance_sheet.py`)
- **Class**: `BalanceSheetLineItemBase`
- **New Fields**:
  - `standardized_name: str | None = None`
  - `is_calculated: bool | None = None`

#### **Income Statement Schemas** (`app/schemas/income_statement.py`)
- **Class**: `IncomeStatementLineItemBase`
- **New Fields**:
  - `standardized_name: str | None = None`
  - `is_calculated: bool | None = None`
  - `is_expense: bool | None = None`

### 3. Migration Plan
- Generate a new Alembic migration script to apply these schema changes to the existing `tiger_cafe.db` SQLite database.

## Section 4: Testing Plan

### 1. New Unit Tests
- **Transformer Client** (`tests/test_tiger_transformer_client.py`):
  - Verify model loading (local vs CPU fallback).
  - Verify inference on sample inputs produces expected `standardized_name`
  - Test edge cases: empty context, missing line items.
- **Validation Logic** (`tests/test_validation_logic.py`):
  - **BS Section Fallback**: Test rule-based fixes and context interpolation for section tags.
  - **IS Residual Solver**: Mock extraction results with sign errors and verify the solver correctly flips `is_expense=null` items to resolve validation failures.

### 2. Updated Integration Tests
- **API Tests** (`tests/test_integration_api.py`):
  - Update assertions to expect strict tokens (e.g., `current_assets`) in `line_category` instead of previous human-readable strings.
  - Mock the `TigerTransformerClient` inference to return deterministic results for speed during standard CI runs.

### 3. Manual Verification
- Process a sample document (e.g., `ADBE`) end-to-end.
- inspecting the database to ensure `standardized_name`, `is_calculated`, `is_operating` and `is_expense` (for income statement only) columns are correctly populated.

## Section 5: Implementation Scope

### 1. New Files
- `app/services/tiger_transformer_client.py`: Client to load model (checking local path first) and run inference.
- `app/data/mappings/*.csv`: Copy of lookup tables from tiger-transformer repo.
- `tests/test_tiger_transformer_client.py`: Unit tests for the new client.
- `tests/test_validation_logic.py`: Unit tests for BS section fallback and IS residual solver.
- `scripts/export_retraining_data.py`: Script to export labeled data for model retraining.

### 2. Database & Schema Updates
- `app/models/balance_sheet.py`: Add `standardized_name`, `is_calculated`.
- `app/models/income_statement.py`: Add `standardized_name`, `is_calculated`, `is_expense`.
- `app/schemas/balance_sheet.py`: Update Pydantic models.
- `app/schemas/income_statement.py`: Update Pydantic models.
- `migrations/versions/xxxx_add_standardized_cols.py`: New Alembic migration (generated).

### 3. Agent Logic Refactor
- `agents/balance_sheet_extractor.py`:
  - Integrate `TigerTransformerClient`.
  - Implement "Section Tag Fallback" pre-processing checks.
  - Update `validate_balance_sheet_calculations`.
  - Remove legacy `get_balance_sheet_llm_insights` and `classify_line_items_llm`.
- `agents/income_statement_extractor.py`:
  - Integrate `TigerTransformerClient`.
  - Implement `is_expense` based normalization logic.
  - Implement "Residual Solver" in validation logic.
  - Remove legacy `get_income_statement_llm_insights` and `classify_line_items_llm`.

### 4. Testing Updates
- `tests/test_integration_api.py`: Update expectations to match new strict tokens (`current_assets` etc) instead of natural language categories.

## Section 6: Implementation Plan

### Phase 1: Database & Schema Preparation
1. Update `app/models/balance_sheet.py` and `app/models/income_statement.py` with new columns.
2. Update `app/schemas/balance_sheet.py` and `app/schemas/income_statement.py` Pydantic models.
3. Generate and apply Alembic migration (`alembic revision --autogenerate`).

### Phase 2: Core Service Implementation
1. Resources Setup
   - Copy `bs_calculated_operating_mapping.csv` and `is_..._mapping.csv` to `app/data/mappings/`.
2. Create `app/services/tiger_transformer_client.py`.
   - Implement `load_model()` (local check -> load).
   - Implement `predict(line_items)` batch inference method.
   - Implement generic mapping logic: `standardized_name` -> `is_calculated`, `is_operating`, `is_expense` using loaded CSVs.
   - Add caching to prevent reloading model on every request.
3. Create `tests/test_tiger_transformer_client.py` and verify basic inference and mapping.

### Phase 3: Balance Sheet Integration
1. **Refactor `agents/balance_sheet_extractor.py`**:
   - **Update Extraction Prompt**:
     - Modify `extract_balance_sheet_llm` and `extract_balance_sheet_llm_with_feedback` to strictly output one of these section tokens in `line_category`:
       - `current_assets`
       - `noncurrent_assets`
       - `current_liabilities`
       - `noncurrent_liabilities`
       - `stockholders_equity`
     - Remove natural language categories (e.g., "Current Assets", "Total Assets").
   - **Integrate Tiger-Transformer**:
     - Rewrite `post_process_balance_sheet_line_items`.
     - **Preprocessing (Section Tag Fallback)**:
       - Validate strict tokens. If a token is invalid/missing, infer it from neighbors (prev/next items).
       - Ensure `total_` lines get the correct section (e.g., "Total Current Assets" -> `current_assets`).
     - **Inference**: Call `TigerTransformerClient.predict_balance_sheet`.
     - **Mapping**: The client service automatically populates `standardized_name` from inference and enriches `is_calculated`, `is_operating` using the loaded CSV lookup table (`bs_calculated_operating_mapping.csv`).
   - **Update Validation Logic**:
     - Modify `validate_balance_sheet_calculations`.
     - Use `standardized_name` (e.g., `total_current_assets`, `total_assets`) to identify anchor values instead of fuzzy name matching.
     - Calculate sums using items where `is_calculated=False` within the corresponding section.
   - **Cleanup**:
     - Remove `get_balance_sheet_llm_insights`.
     - Remove `classify_line_items_llm`.

2. **Testing & Verification**:
   - Create `tests/test_validation_logic.py` to test section fallback and calculation logic.
   - Run `tests/test_integration_api.py`.
   - Update API integration tests to expect strict section tokens in responses.

### Phase 4: Income Statement Integration
1. **Refactor `agents/income_statement_extractor.py`**:
   - **Update Extraction Prompt**:
     - Modify prompts to strictly output `income_statement` as the `line_category` for all items.
   - **Integrate Tiger-Transformer**:
     - Rewrite `post_process_income_statement_line_items`.
     - Call `TigerTransformerClient.predict_income_statement`.
     - **Mapping**: The client service automatically populates `standardized_name` from inference and enriches `is_calculated`, `is_operating`, `is_expense` using the loaded CSV lookup table (`is_calculated_operating_expense_mapping.csv`).
   - **Implement Normalization Logic**:
     - **Sign Flipping**: Ensure confirmed expenses (`is_expense=True`) are negative. If extracted value is positive, multiply by -1.
     - **Ambiguous Items (`is_expense=None`)**: Leave signs exactly as extracted from the document initially. Do not apply a default rule.
   - **Update Validation (Residual Solver)**:
     - in `validate_income_statement_calculations`:
     - If initial validation fails (Net Income check), calculate `Residual = Calculated_Net_Income - Reported_Net_Income`.
     - **Solver Logic**: Check combinations of `is_expense=None` items. If flipping the sign of one or more ambiguous items resolves the `Residual` (difference becomes 0 within tolerance), apply those flips, update the values, and mark the statement as valid.
   - **Cleanup**:
     - Remove `get_income_statement_llm_insights`.
     - Remove `classify_line_items_llm`.

2. **Testing & Verification**:
   - Update `tests/test_validation_logic.py` with IS specific cases (sign flipping, residual solving).
   - Run `tests/test_integration_api.py` and fix failures.

### Phase 5: Cleanup & Tools
1. Remove usage of old `classify_line_items_llm` and `get_..._llm_insights`.
2. Create `scripts/export_retraining_data.py`.
3. Final full E2E test run.
