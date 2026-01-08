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
Stores user information from Google OAuth authentication.

- `id` (String, Primary Key): Google user ID (sub claim from JWT)
- `email` (String, Unique, Indexed): User email address
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

## Notes

- The database defaults to SQLite (`tiger_cafe.db`) via `DATABASE_URL` in `.env`.
- Historical migrations are archived in `migrations_archive/`. New schema changes should be reflected in models + baseline migration updates.
