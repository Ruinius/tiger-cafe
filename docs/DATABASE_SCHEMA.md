# Database Schema

This document summarizes the current SQLite schema for Tiger-Cafe and points to the model definitions that act as the source of truth.

## Source of Truth

SQLAlchemy models live in `app/models/`:

- `app/models/user.py`
- `app/models/company.py`
- `app/models/document.py`
- `app/models/balance_sheet.py`
- `app/models/income_statement.py`
- `app/models/historical_calculation.py`
- `app/models/financial_metric.py`
- `app/models/analysis_result.py`

If you need to update the schema, change the model definitions first, then regenerate the baseline schema with `migrate_baseline_schema.py`.

## Tables

### `users`
Stores user information for authentication.

- `id` (String, Primary Key): Unique user ID
- `email` (String, Unique, Indexed): User email address
- `hashed_password` (String, Nullable): BCrypt hashed password
- `name` (String, Nullable): Display name
- `picture` (String, Nullable): Profile image URL
- `created_at` (DateTime): Account creation timestamp
- `updated_at` (DateTime, Nullable): Last update timestamp
- `is_active` (Boolean): Account active status

### `companies`
Stores company information.

- `id` (String, Primary Key): Unique company identifier
- `name` (String, Indexed): Company name
- `ticker` (String, Nullable, Indexed): Stock ticker symbol
- `created_at` (DateTime): Record creation timestamp
- `updated_at` (DateTime, Nullable): Last update timestamp

**Relationships:**
- One-to-many with `documents`
- One-to-many with `financial_metrics`
- One-to-many with `analysis_results`

### `documents`
Stores uploaded document metadata and processing status.

- `id` (String, Primary Key): Unique document identifier
- `user_id` (String, Foreign Key → `users.id`, Indexed): Document owner
- `company_id` (String, Foreign Key → `companies.id`, Indexed): Associated company
- `filename` (String): Original filename
- `file_path` (String): Path to stored PDF file
- `document_type` (Enum): `earnings_announcement`, `quarterly_filing`, `annual_filing`, `press_release`, `analyst_report`, `news_article`, `transcript`, `other`
- `time_period` (String, Nullable): Time period (e.g., “Q3 2023”)
- `unique_id` (String, Nullable, Indexed): Dedupe identifier
- `indexing_status` (Enum): `pending`, `uploading`, `classifying`, `classified`, `indexing`, `indexed`, `error`
- `analysis_status` (Enum): `pending`, `processing`, `processed`, `error`
- `duplicate_detected` (Boolean): Duplicate flag
- `existing_document_id` (String, Nullable): Duplicate reference
- `summary` (Text, Nullable): LLM-generated summary
- `page_count` (Integer, Nullable): Number of pages
- `character_count` (Integer, Nullable): Character count of extracted text
- `uploaded_at` (DateTime): Upload timestamp
- `indexed_at` (DateTime, Nullable): Indexing completion timestamp
- `processed_at` (DateTime, Nullable): Analysis completion timestamp

**Relationships:**
- Many-to-one with `users`
- Many-to-one with `companies`
- One-to-one with `balance_sheet`
- One-to-one with `income_statement`
- One-to-one with `organic_growth`
- One-to-one with `historical_calculation`
- One-to-many with `amortization`
- One-to-many with `other_assets`
- One-to-many with `other_liabilities`
- One-to-many with `non_operating_classification`

### `balance_sheets`
Stores extracted balance sheet data from documents.

- `id` (String, Primary Key): Unique balance sheet identifier
- `document_id` (String, Foreign Key → `documents.id`, Indexed, Unique): Associated document
- `time_period` (String, Nullable): Time period (e.g., "Q3 2023")
- `currency` (String, Nullable): Currency code (e.g., "USD", "EUR")
- `unit` (String, Nullable): Unit of measurement ("ones", "thousands", "millions", "billions", "ten_thousands")
- `extraction_date` (DateTime): Extraction timestamp
- `is_valid` (Boolean): Validation status
- `validation_errors` (Text, Nullable): JSON string of validation errors
- `chunk_index` (Integer, Nullable): Chunk index used for extraction

**Relationships:**
- One-to-one with `documents`
- One-to-many with `balance_sheet_line_items`

### `balance_sheet_line_items`
Stores individual line items from balance sheets.

- `id` (String, Primary Key): Unique line item identifier
- `balance_sheet_id` (String, Foreign Key → `balance_sheets.id`, Indexed): Parent balance sheet
- `line_name` (String): Line item name (e.g., "Cash and Cash Equivalents")
- `line_value` (Numeric 20,2): Monetary value
- `line_category` (String, Nullable): Section token (e.g., "current_assets", "stockholders_equity")
- `standardized_name` (String, Nullable): Standardized name from transformer (e.g., "cash_and_equivalents")
- `is_calculated` (Boolean, Nullable): Is this a total/subtotal?
- `is_operating` (Boolean, Nullable): Operating vs non-operating classification
- `line_order` (Integer): Display order

**Relationships:**
- Many-to-one with `balance_sheets`

### `income_statements`
Stores extracted income statement data from documents.

- `id` (String, Primary Key): Unique income statement identifier
- `document_id` (String, Foreign Key → `documents.id`, Indexed, Unique): Associated document
- `time_period` (String, Nullable): Time period (e.g., "Q3 2023")
- `currency` (String, Nullable): Currency code
- `unit` (String, Nullable): Unit of measurement
- `extraction_date` (DateTime): Extraction timestamp
- `revenue_prior_year` (Numeric 20,2, Nullable): Prior year revenue for comparison
- `revenue_prior_year_unit` (String, Nullable): Unit for prior year revenue
- `revenue_growth_yoy` (Numeric 10,4, Nullable): **Year-over-year revenue growth percentage (simple growth)**
- `basic_shares_outstanding` (Numeric 20,2, Nullable): Basic shares outstanding
- `basic_shares_outstanding_unit` (String, Nullable): Unit for basic shares
- `diluted_shares_outstanding` (Numeric 20,2, Nullable): Diluted shares outstanding
- `diluted_shares_outstanding_unit` (String, Nullable): Unit for diluted shares
- `amortization` (Numeric 20,2, Nullable): Amortization value
- `amortization_unit` (String, Nullable): Unit for amortization
- `is_valid` (Boolean): Validation status
- `validation_errors` (Text, Nullable): JSON string of validation errors
- `chunk_index` (Integer, Nullable): Chunk index used for extraction

**Relationships:**
- One-to-one with `documents`
- One-to-many with `income_statement_line_items`

### `income_statement_line_items`
Stores individual line items from income statements.

- `id` (String, Primary Key): Unique line item identifier
- `income_statement_id` (String, Foreign Key → `income_statements.id`, Indexed): Parent income statement
- `line_name` (String): Line item name (e.g., "Revenue", "Cost of Goods Sold")
- `line_value` (Numeric 20,2): Monetary value
- `line_category` (String, Nullable): Section token (e.g., "income_statement")
- `standardized_name` (String, Nullable): Standardized name from transformer
- `is_calculated` (Boolean, Nullable): Is this a total/subtotal?
- `is_expense` (Boolean, Nullable): Is this an expense item?
- `is_operating` (Boolean, Nullable): Operating vs non-operating classification
- `line_order` (Integer): Display order

**Relationships:**
- Many-to-one with `income_statements`

### `organic_growth`
Stores organic growth analysis extracted from documents.

- `id` (String, Primary Key): Unique organic growth identifier
- `document_id` (String, Foreign Key → `documents.id`, Indexed): Associated document
- `time_period` (String, Nullable): Time period
- `currency` (String, Nullable): Currency code
- `prior_period_revenue` (Numeric 20,2, Nullable): Prior period revenue
- `prior_period_revenue_unit` (String, Nullable): Unit for prior period revenue
- `current_period_revenue` (Numeric 20,2, Nullable): Current period revenue
- `current_period_revenue_unit` (String, Nullable): Unit for current period revenue
- `simple_revenue_growth` (Numeric 10,4, Nullable): **Simple revenue growth percentage**
- `acquisition_revenue_impact` (Numeric 20,2, Nullable): Revenue impact from acquisitions
- `acquisition_revenue_impact_unit` (String, Nullable): Unit for acquisition impact
- `current_period_adjusted_revenue` (Numeric 20,2, Nullable): Revenue adjusted for acquisitions
- `current_period_adjusted_revenue_unit` (String, Nullable): Unit for adjusted revenue
- `organic_revenue_growth` (Numeric 10,4, Nullable): **Organic revenue growth percentage (excluding M&A)**
- `chunk_index` (Integer, Nullable): Chunk index used for extraction
- `is_valid` (Boolean): Validation status
- `validation_errors` (Text, Nullable): JSON string of validation errors
- `extraction_date` (DateTime): Extraction timestamp

**Relationships:**
- One-to-one with `documents`

### `amortization`
Stores amortization and non-GAAP reconciliation data.

- `id` (String, Primary Key): Unique amortization identifier
- `document_id` (String, Foreign Key → `documents.id`, Indexed): Associated document
- `time_period` (String, Nullable): Time period
- `currency` (String, Nullable): Currency code
- `chunk_index` (Integer, Nullable): Chunk index used for extraction
- `is_valid` (Boolean): Validation status
- `validation_errors` (Text, Nullable): JSON string of validation errors
- `extraction_date` (DateTime): Extraction timestamp

**Relationships:**
- Many-to-one with `documents`
- One-to-many with `amortization_line_items`

### `amortization_line_items`
Stores individual amortization and reconciliation line items.

- `id` (String, Primary Key): Unique line item identifier
- `amortization_id` (String, Foreign Key → `amortization.id`, Indexed): Parent amortization record
- `line_name` (String): Line item name
- `line_value` (Numeric 20,2): Monetary value
- `unit` (String, Nullable): Unit of measurement
- `is_operating` (Boolean, Nullable): Operating classification
- `category` (String, Nullable): Item category
- `line_order` (Integer): Display order

**Relationships:**
- Many-to-one with `amortization`

### `other_assets`
Stores detailed breakdown of "Other Assets" from balance sheets.

- `id` (String, Primary Key): Unique other assets identifier
- `document_id` (String, Foreign Key → `documents.id`, Indexed): Associated document
- `time_period` (String, Nullable): Time period
- `currency` (String, Nullable): Currency code
- `chunk_index` (Integer, Nullable): Chunk index used for extraction
- `is_valid` (Boolean): Validation status
- `validation_errors` (Text, Nullable): JSON string of validation errors
- `extraction_date` (DateTime): Extraction timestamp

**Relationships:**
- Many-to-one with `documents`
- One-to-many with `other_assets_line_items`

### `other_assets_line_items`
Stores individual line items from other assets breakdown.

- `id` (String, Primary Key): Unique line item identifier
- `other_assets_id` (String, Foreign Key → `other_assets.id`, Indexed): Parent other assets record
- `line_name` (String): Line item name
- `line_value` (Numeric 20,2): Monetary value
- `unit` (String, Nullable): Unit of measurement
- `is_operating` (Boolean, Nullable): Operating classification
- `category` (String, Nullable): Item category
- `line_order` (Integer): Display order

**Relationships:**
- Many-to-one with `other_assets`

### `other_liabilities`
Stores detailed breakdown of "Other Liabilities" from balance sheets.

- `id` (String, Primary Key): Unique other liabilities identifier
- `document_id` (String, Foreign Key → `documents.id`, Indexed): Associated document
- `time_period` (String, Nullable): Time period
- `currency` (String, Nullable): Currency code
- `chunk_index` (Integer, Nullable): Chunk index used for extraction
- `is_valid` (Boolean): Validation status
- `validation_errors` (Text, Nullable): JSON string of validation errors
- `extraction_date` (DateTime): Extraction timestamp

**Relationships:**
- Many-to-one with `documents`
- One-to-many with `other_liabilities_line_items`

### `other_liabilities_line_items`
Stores individual line items from other liabilities breakdown.

- `id` (String, Primary Key): Unique line item identifier
- `other_liabilities_id` (String, Foreign Key → `other_liabilities.id`, Indexed): Parent other liabilities record
- `line_name` (String): Line item name
- `line_value` (Numeric 20,2): Monetary value
- `unit` (String, Nullable): Unit of measurement
- `is_operating` (Boolean, Nullable): Operating classification
- `category` (String, Nullable): Item category
- `line_order` (Integer): Display order

**Relationships:**
- Many-to-one with `other_liabilities`

### `non_operating_classification`
Stores classification of non-operating balance sheet items for DCF equity bridge.

- `id` (String, Primary Key): Unique classification identifier
- `document_id` (String, Foreign Key → `documents.id`, Indexed): Associated document
- `time_period` (String, Nullable): Time period
- `extraction_date` (DateTime): Classification timestamp

**Relationships:**
- Many-to-one with `documents`
- One-to-many with `non_operating_classification_items`

### `non_operating_classification_items`
Stores individual non-operating items with their categories.

- `id` (String, Primary Key): Unique item identifier
- `classification_id` (String, Foreign Key → `non_operating_classification.id`, Indexed): Parent classification
- `line_name` (String): Line item name
- `line_value` (Numeric 20,2, Nullable): Monetary value
- `unit` (String, Nullable): Unit of measurement
- `category` (String, Nullable): Classification category (e.g., "cash", "debt", "short_term_investments")
- `source` (String, Nullable): Source table (e.g., "balance_sheet", "other_assets")
- `line_order` (Integer): Display order

**Relationships:**
- Many-to-one with `non_operating_classification`

### `financial_metrics`
Stores calculated metrics for companies.

- `id` (String, Primary Key): Unique metric identifier
- `company_id` (String, Foreign Key → `companies.id`, Indexed): Associated company
- `metric_name` (String, Indexed): Metric name (e.g., `organic_growth`, `operating_margin`)
- `period` (String, Indexed): Time period (e.g., “FY 2023”)
- `period_date` (Date, Nullable, Indexed): Specific date for the period
- `value` (Float): Metric value
- `unit` (String, Nullable): Unit of measurement (e.g., `percentage`, `ratio`, `dollars`)
- `source_document_id` (String, Foreign Key → `documents.id`, Nullable): Source document
- `calculated_at` (DateTime): Calculation timestamp

### `financial_assumptions`
Stores user-defined assumptions for financial modeling (DCF).

- `id` (String, Primary Key): Unique identifier
- `company_id` (String, Foreign Key → `companies.id`, Indexed, Unique): Associated company
- `revenue_growth_stage1` (Numeric 10,4): Revenue growth rate for years 1-5
- `revenue_growth_stage2` (Numeric 10,4): Revenue growth rate for years 6-10
- `revenue_growth_terminal` (Numeric 10,4): Terminal revenue growth rate
- `ebita_margin_stage1` (Numeric 10,4): EBITA margin for years 1-5
- `ebita_margin_stage2` (Numeric 10,4): EBITA margin for years 6-10
- `ebita_margin_terminal` (Numeric 10,4): Terminal EBITA margin
- `marginal_capital_turnover_stage1` (Numeric 10,4): MCT for years 1-5
- `marginal_capital_turnover_stage2` (Numeric 10,4): MCT for years 6-10
- `marginal_capital_turnover_terminal` (Numeric 10,4): Terminal MCT
- `adjusted_tax_rate` (Numeric 10,4): Projected tax rate
- `wacc` (Numeric 10,4): Weighted Average Cost of Capital

**Relationships:**
- One-to-one with `companies`

### `analysis_results`
Stores analysis results (valuation, sensitivity, etc.).

- `id` (String, Primary Key): Unique result identifier
- `company_id` (String, Foreign Key → `companies.id`, Indexed): Associated company
- `analysis_type` (String, Indexed): Type (e.g., `intrinsic_value`, `sensitivity`, `market_belief`)
- `completed_at` (DateTime): Analysis completion timestamp
- `assumptions` (JSON, Nullable): Input assumptions
- `results` (JSON): Calculation results
- `summary` (Text, Nullable): LLM-generated summary

### `historical_calculations`
Stores calculated historical financial metrics for documents.

- `id` (String, Primary Key): Unique calculation identifier
- `document_id` (String, Foreign Key → `documents.id`, Indexed, Unique): Associated document
- `time_period` (String, Nullable): Time period (e.g., "Q3 2023", "FY 2023")
- `currency` (String, Nullable): Currency code (e.g., "USD", "EUR")
- `unit` (String, Nullable): Unit of measurement ("ones", "thousands", "millions", "billions", or "ten_thousands")
- `calculated_at` (DateTime): Calculation timestamp
- `net_working_capital` (Numeric(20, 2), Nullable): Calculated net working capital
- `net_working_capital_breakdown` (Text, Nullable): JSON string breakdown
- `net_long_term_operating_assets` (Numeric(20, 2), Nullable): Calculated net long-term operating assets
- `net_long_term_operating_assets_breakdown` (Text, Nullable): JSON string breakdown
- `invested_capital` (Numeric(20, 2), Nullable): Calculated invested capital
- `capital_turnover` (Numeric(10, 4), Nullable): Calculated capital turnover ratio
- `ebita` (Numeric(20, 2), Nullable): Calculated EBITA
- `ebita_breakdown` (Text, Nullable): JSON string breakdown
- `ebita_margin` (Numeric(10, 4), Nullable): Calculated EBITA margin
- `effective_tax_rate` (Numeric(10, 4), Nullable): Effective tax rate
- `adjusted_tax_rate` (Numeric(10, 4), Nullable): Adjusted tax rate
- `adjusted_tax_rate_breakdown` (Text, Nullable): JSON string breakdown
- `nopat` (Numeric(20, 2), Nullable): Net Operating Profit After Tax
- `roic` (Numeric(10, 4), Nullable): Return on Invested Capital
- `calculation_notes` (Text, Nullable): JSON string for any calculation notes or warnings

**Relationships:**
- One-to-one with `documents`

### `valuations`
Stores historical valuation snapshots for tracking fair value estimates over time.

- `id` (String, Primary Key): Unique valuation identifier
- `company_id` (String, Foreign Key → `companies.id`, Indexed): Associated company
- `user_id` (String, Foreign Key → `users.id`, Indexed): User who saved the valuation
- `date` (DateTime): Valuation snapshot timestamp (defaults to current time)
- `fair_value` (Numeric(20, 2)): Fair value per share at time of valuation
- `share_price_at_time` (Numeric(20, 2), Nullable): Market share price at time of valuation
- `percent_undervalued` (Numeric(10, 4), Nullable): Calculated percentage difference (Fair - Market) / Market

**Relationships:**
- Many-to-one with `companies`
- Many-to-one with `users`

## Enums

### `DocumentType`
- `earnings_announcement`
- `quarterly_filing`
- `annual_filing`
- `press_release`
- `analyst_report`
- `news_article`
- `transcript`
- `other`

### `ProcessingStatus`
- `pending`
- `uploading`
- `classifying`
- `classified` - Terminal state for documents that have been classified but indexing was skipped (non-earnings announcements)
- `indexing`
- `indexed`
- `processing`
- `processed`
- `error`

## Indexes

- `users.email`: Unique index for email lookups
- `companies.name`: Index for company name searches
- `companies.ticker`: Index for ticker symbol lookups
- `documents.user_id`: Index for user document queries
- `documents.company_id`: Index for company document queries
- `documents.unique_id`: Unique index for deduplication
- `financial_metrics.company_id`: Index for company metric queries
- `financial_metrics.metric_name`: Index for metric type queries
- `financial_metrics.period`: Index for time period queries
- `financial_assumptions.company_id`: Unique index for company assumptions
- `analysis_results.company_id`: Index for company analysis queries
- `historical_calculations.document_id`: Unique index for document calculation queries
- `valuations.company_id`: Index for company valuation queries
- `valuations.user_id`: Index for user valuation queries

## Notes

- The database defaults to SQLite (`tiger_cafe.db`) via `DATABASE_URL` in `.env`.
- Historical migrations are archived in `migrations_archive/`. New schema changes should be reflected in models + baseline migration updates.
