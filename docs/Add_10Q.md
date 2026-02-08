# Document Processing Pipelines

This document describes the full extraction pipeline for different document types in the Tiger Cafe system, based on the `extraction_orchestrator.py` service.

---

## Section 1: Earnings Announcement Pipeline

When an **Earnings Announcement** document is uploaded, the system executes the following pipeline:

### Phase 1: Ingestion (`run_ingestion_pipeline`)
1. **Document Classification** - The document is classified using the `process_document` function with `DocumentProcessingMode.FULL`
2. **Document Indexing** - The document is indexed and chunked for extraction
3. **Trigger Extraction** - After successful ingestion, automatically triggers the full extraction pipeline

### Phase 2-3: Extraction (`run_full_extraction_pipeline`)

#### 2.1 Balance Sheet Extraction (`extract_balance_sheet_task`)
- **Eligibility Check**: Earnings announcements ARE eligible for balance sheet extraction
- **Process**:
  - Deletes any existing balance sheet data for the document
  - Calls `extract_balance_sheet` agent with document metadata (file_path, time_period, document_type, period_end_date)
  - Stores the `balance_sheet_chunk_index` in progress store for use by income statement extraction
  - Validates extracted line items (must have at least 1 line item)
  - Saves `BalanceSheet` record with metadata (time_period, currency, unit, chunk_index, validation status)
  - Saves all `BalanceSheetLineItem` records with standardized fields
  - Updates milestone status to COMPLETED, WARNING (if validation errors), or ERROR

#### 2.2 Income Statement Extraction (`extract_income_statement_task`)
- **Eligibility Check**: Earnings announcements ARE eligible for income statement extraction
- **Process**:
  - Deletes any existing income statement data for the document
  - Retrieves `balance_sheet_chunk_index` from progress store (if available)
  - Calls `extract_income_statement` agent with document metadata and balance sheet chunk hint
  - Validates extracted line items (must have at least 1 line item)
  - Saves `IncomeStatement` record with metadata including `revenue_prior_year` and `revenue_prior_year_unit`
  - Saves all `IncomeStatementLineItem` records with standardized fields (including `is_expense` flag)
  - Updates milestone status to COMPLETED, WARNING, or ERROR

#### 2.3 Additional Items Extraction (`extract_additional_items_task`)

**2.3.1 Shares Outstanding**
- Retrieves `income_statement_chunk_index` if available
- Calls `extract_shares_outstanding` agent
- **Validation**: Values must be > 1,000,000 shares (in "ones" unit) to prevent false positives
- Normalizes units to match Income Statement unit if available
- Saves `SharesOutstanding` record with basic and diluted shares
- Status: COMPLETED, WARNING (if not found or too small), or ERROR

**2.3.2 Organic Growth** (Earnings Announcements ONLY)
- **Eligibility**: Only runs for EARNINGS_ANNOUNCEMENT and QUARTERLY_FILING document types
- Prepares income statement data as a dictionary including line items and `revenue_prior_year`
- Calls `extract_organic_growth` agent with income statement context
- Saves `OrganicGrowth` record with:
  - Prior period revenue
  - Current period revenue
  - Simple revenue growth %
  - Acquisition revenue impact
  - Organic revenue growth %
- Updates `IncomeStatement.revenue_prior_year` if missing
- Status: COMPLETED, ERROR (if comparative revenue missing), or SKIPPED

**2.3.3 GAAP Reconciliation**
- Calls `extract_gaap_reconciliation` agent
- Saves `GAAPReconciliation` record with line items for Non-GAAP to GAAP adjustments
- Status: COMPLETED, SKIPPED (if not found), or WARNING

**2.3.4 Amortization** (SKIPPED for Earnings Announcements)
- Status: SKIPPED with message "Amortization skipped for earnings announcement"

**2.3.5 Other Assets** (SKIPPED for Earnings Announcements)
- Status: SKIPPED with message "Other assets skipped for earnings announcement"

**2.3.6 Other Liabilities** (SKIPPED for Earnings Announcements)
- Status: SKIPPED with message "Other liabilities skipped for earnings announcement"

#### 2.4 Non-Operating Classification (`classify_non_operating_items_task`)
- Calls the classification service to separate operating from non-operating items
- Updates `is_operating` flags on balance sheet and income statement line items
- Pipeline continues even if classification fails

### Phase 4: Analysis (`run_analysis_pipeline`)

#### 4.1 Calculate Value Metrics (Document Level)
- Calls `calculate_and_save_historical_calculations` to compute:
  - ROIC (Return on Invested Capital)
  - EBITA (Earnings Before Interest, Taxes, and Amortization)
  - Other financial metrics
- Saves `HistoricalCalculation` record
- Status: COMPLETED or ERROR

#### 4.2 Company-Level Milestones (Marked as Ready)
- **Update Historical Data**: Marked as COMPLETED - "Ready for historical data aggregation"
- **Update Assumptions**: Marked as COMPLETED - "Ready for assumptions update"
- **Calculate Intrinsic Value**: Marked as COMPLETED - "Ready for intrinsic value calculation"
- These are GET endpoints called by the frontend when viewing the company page

### Final Status Update
- Document status set to `DocumentStatus.PROCESSING_COMPLETE`
- `analysis_status` set to `ProcessingStatus.PROCESSED`
- `processed_at` timestamp updated

---

## Section 2: 10-Q (Quarterly Filing) Pipeline

When a **10-Q (Quarterly Filing)** document is uploaded, the system executes a MORE COMPREHENSIVE pipeline than earnings announcements:

### Phase 1: Ingestion (`run_ingestion_pipeline`)
**IDENTICAL to Earnings Announcement Pipeline**
1. Document Classification
2. Document Indexing
3. Trigger Extraction

### Phase 2-3: Extraction (`run_full_extraction_pipeline`)

#### 2.1 Balance Sheet Extraction (`extract_balance_sheet_task`)
**IDENTICAL to Earnings Announcement Pipeline**
- Eligibility: 10-Q filings ARE eligible
- Same extraction and validation process

#### 2.2 Income Statement Extraction (`extract_income_statement_task`)
**IDENTICAL to Earnings Announcement Pipeline**
- Eligibility: 10-Q filings ARE eligible
- Same extraction and validation process

#### 2.3 Additional Items Extraction (`extract_additional_items_task`)

**2.3.1 Shares Outstanding**
**IDENTICAL to Earnings Announcement Pipeline**

**2.3.2 Organic Growth** (10-Q Filings INCLUDED)
**IDENTICAL to Earnings Announcement Pipeline**
- 10-Q filings ARE eligible for organic growth extraction
- Same process as earnings announcements

**2.3.3 GAAP Reconciliation**
**IDENTICAL to Earnings Announcement Pipeline**

**2.3.4 Amortization** (EXTRACTED for 10-Q Filings - DIFFERENT from Earnings)
- **Eligibility**: Only runs for QUARTERLY_FILING and ANNUAL_FILING document types
- Calls `extract_amortization` agent
- Saves `Amortization` record with line items for intangible asset amortization schedules
- Status: COMPLETED, SKIPPED (if not found), or ERROR

**2.3.5 Other Assets** (EXTRACTED for 10-Q Filings - DIFFERENT from Earnings)
- **Eligibility**: Only runs for QUARTERLY_FILING and ANNUAL_FILING document types
- **Query Preparation**:
  - Scans balance sheet for "Other Assets" line items in current and non-current categories
  - Builds query terms list: ["Other Assets", "Prepaid", "Other current assets", "Other non-current assets", ...]
  - Extracts expected totals from balance sheet for validation
- Calls `extract_other_assets` agent with query terms and expected totals
- Saves `OtherAssets` record with detailed line item breakdowns
- Status: COMPLETED, SKIPPED (if not found), or ERROR

**2.3.6 Other Liabilities** (EXTRACTED for 10-Q Filings - DIFFERENT from Earnings)
- **Eligibility**: Only runs for QUARTERLY_FILING and ANNUAL_FILING document types
- **Query Preparation**:
  - Scans balance sheet for "Other Liabilities" line items in current and non-current categories
  - Builds query terms list: ["Other Liabilities", "Accrued", "Other current liabilities", "Other non-current liabilities", ...]
  - Extracts expected totals from balance sheet for validation
- Calls `extract_other_liabilities` agent with query terms and expected totals
- Saves `OtherLiabilities` record with detailed line item breakdowns
- Status: COMPLETED, SKIPPED (if not found), or ERROR

#### 2.4 Non-Operating Classification (`classify_non_operating_items_task`)
**IDENTICAL to Earnings Announcement Pipeline**

### Phase 4: Analysis (`run_analysis_pipeline`)
**IDENTICAL to Earnings Announcement Pipeline**
- Calculate Value Metrics
- Mark Company-Level Milestones as Ready

### Final Status Update
**IDENTICAL to Earnings Announcement Pipeline**

---

## Key Differences: Earnings Announcement vs 10-Q

| Feature | Earnings Announcement | 10-Q (Quarterly Filing) |
|---------|----------------------|------------------------|
| **Balance Sheet** | ✅ Extracted | ✅ Extracted |
| **Income Statement** | ✅ Extracted | ✅ Extracted |
| **Shares Outstanding** | ✅ Extracted | ✅ Extracted |
| **Organic Growth** | ✅ Extracted | ✅ Extracted |
| **GAAP Reconciliation** | ✅ Extracted | ✅ Extracted |
| **Amortization** | ❌ SKIPPED | ✅ Extracted |
| **Other Assets** | ❌ SKIPPED | ✅ Extracted (with balance sheet context) |
| **Other Liabilities** | ❌ SKIPPED | ✅ Extracted (with balance sheet context) |

**Rationale**: 10-Q filings are comprehensive regulatory documents that include detailed footnotes and schedules for amortization, other assets, and other liabilities. Earnings announcements are typically shorter press releases that focus on headline financial metrics and may not include these detailed breakdowns.

---

## Error Handling Strategy

The pipeline is designed with **graceful degradation**:

1. **Balance Sheet Failure**: Logs error, updates milestone to ERROR, but continues to Income Statement
2. **Income Statement Failure**: Logs error, updates milestone to ERROR, but continues to Additional Items
3. **Additional Items Failures**: Each item (shares, organic growth, etc.) fails independently without stopping the pipeline
4. **Classification Failure**: Logs error but continues to Analysis phase
5. **Analysis Failure**: Logs error, marks document as EXTRACTION_FAILED

This ensures maximum data extraction even when individual components fail.

---

## Data Flow and Dependencies

```
Document Upload
    ↓
Phase 1: Ingestion (Classification + Indexing)
    ↓
Phase 2: Core Financial Statements
    ├─ Balance Sheet → stores chunk_index
    └─ Income Statement → uses balance_sheet_chunk_index hint
    ↓
Phase 3: Additional Items
    ├─ Shares Outstanding → uses income_statement_chunk_index
    ├─ Organic Growth → uses income_statement line items + revenue_prior_year
    ├─ GAAP Reconciliation
    ├─ Amortization (10-Q only)
    ├─ Other Assets (10-Q only) → uses balance_sheet line items for query
    └─ Other Liabilities (10-Q only) → uses balance_sheet line items for query
    ↓
Phase 3: Classification
    └─ Non-Operating Classification → updates is_operating flags
    ↓
Phase 4: Analysis
    ├─ Calculate Value Metrics (ROIC, EBITA)
    └─ Mark Company-Level Milestones as Ready
    ↓
Document Status: PROCESSING_COMPLETE
```

**Key Dependencies**:
- Income Statement extraction benefits from `balance_sheet_chunk_index` to locate the correct document section
- Shares Outstanding extraction benefits from `income_statement_chunk_index`
- Organic Growth extraction REQUIRES income statement data (line items and revenue_prior_year)
- Other Assets/Liabilities extraction uses balance sheet line items to build targeted query terms
- Value metrics calculation requires completed financial statements
