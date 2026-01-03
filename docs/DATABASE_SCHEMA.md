# Database Schema

This document describes the database schema for Tiger-Cafe.

## Tables

### users
Stores user information from Google OAuth authentication.

- `id` (String, Primary Key): Google user ID (sub claim from JWT)
- `email` (String, Unique, Indexed): User email address
- `name` (String, Nullable): User's display name
- `picture` (String, Nullable): URL to user's profile picture
- `created_at` (DateTime): Account creation timestamp
- `updated_at` (DateTime, Nullable): Last update timestamp
- `is_active` (Boolean): Account active status

### companies
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

### documents
Stores uploaded document metadata and processing status.

- `id` (String, Primary Key): Unique document identifier
- `user_id` (String, Foreign Key -> users.id, Indexed): Owner of the document
- `company_id` (String, Foreign Key -> companies.id, Indexed): Associated company
- `filename` (String): Original filename
- `file_path` (String): Path to stored PDF file
- `document_type` (Enum): Type of document (earnings_announcement, quarterly_filing, annual_filing, press_release, analyst_report, news_article, other)
- `time_period` (String, Nullable): Time period (e.g., "Q3 2023", "FY 2023")
- `indexing_status` (Enum): Status of embedding/indexing (pending, indexing, indexed, error)
- `analysis_status` (Enum): Status of financial analysis (pending, processing, processed, error)
- `summary` (Text, Nullable): LLM-generated summary from initial upload
- `page_count` (Integer, Nullable): Number of pages in the document
- `character_count` (Integer, Nullable): Character count of extracted text
- `uploaded_at` (DateTime): Upload timestamp
- `indexed_at` (DateTime, Nullable): Indexing completion timestamp
- `processed_at` (DateTime, Nullable): Analysis completion timestamp

**Relationships:**
- Many-to-one with `users`
- Many-to-one with `companies`

### financial_metrics
Stores calculated financial metrics for companies.

- `id` (String, Primary Key): Unique metric identifier
- `company_id` (String, Foreign Key -> companies.id, Indexed): Associated company
- `metric_name` (String, Indexed): Name of the metric (e.g., "organic_growth", "operating_margin", "capital_turnover")
- `period` (String, Indexed): Time period (e.g., "Q3 2023", "FY 2023")
- `period_date` (Date, Nullable, Indexed): Specific date for the period
- `value` (Float): Metric value
- `unit` (String, Nullable): Unit of measurement (e.g., "percentage", "ratio", "dollars")
- `source_document_id` (String, Foreign Key -> documents.id, Nullable): Source document
- `calculated_at` (DateTime): Calculation timestamp

**Relationships:**
- Many-to-one with `companies`
- Many-to-one with `documents` (optional)

### analysis_results
Stores analysis results (valuation, sensitivity, etc.).

- `id` (String, Primary Key): Unique result identifier
- `company_id` (String, Foreign Key -> companies.id, Indexed): Associated company
- `analysis_type` (String, Indexed): Type of analysis (e.g., "intrinsic_value", "sensitivity", "market_belief")
- `completed_at` (DateTime): Analysis completion timestamp
- `assumptions` (JSON, Nullable): Input assumptions for the analysis
- `results` (JSON): Calculation results
- `summary` (Text, Nullable): LLM-generated summary of the analysis

**Relationships:**
- Many-to-one with `companies`

## Enums

### DocumentType
- `earnings_announcement`
- `quarterly_filing`
- `annual_filing`
- `press_release`
- `analyst_report`
- `news_article`
- `other`

### ProcessingStatus
- `pending`
- `indexing` / `processing`
- `indexed` / `processed`
- `error`

## Indexes

- `users.email`: Unique index for email lookups
- `companies.name`: Index for company name searches
- `companies.ticker`: Index for ticker symbol lookups
- `documents.user_id`: Index for user's document queries
- `documents.company_id`: Index for company document queries
- `financial_metrics.company_id`: Index for company metric queries
- `financial_metrics.metric_name`: Index for metric type queries
- `financial_metrics.period`: Index for time period queries
- `analysis_results.company_id`: Index for company analysis queries

