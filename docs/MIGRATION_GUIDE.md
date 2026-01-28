# Database Migration Guide

## Baseline Migration

All major historical migrations have been consolidated into a single baseline migration: `migrate_baseline_schema.py`. This script initializes a fresh database with the complete schema current as of January 2026.

### Incorporated Migrations (Archived)

The following historical migrations (24 total) have been consolidated into the baseline schema and moved to `migrations_archive/`:

#### Core Financial Tables
1.  **migrate_add_balance_sheet_tables.py**: Foundation for BS data.
2.  **migrate_add_income_statement_tables.py**: Foundation for IS data.
3.  **migrate_add_historical_calculations_table.py**: Foundation for analysis metrics.
4.  **migrate_add_unit_fields.py**: Unit handling (thousands, millions, etc.).
5.  **add_currency_fields.py**: Currency and unit fields across all statements.
6.  **migrate_rename_total_to_basic_shares.py**: Shared column consistency.

#### Document & System Infrastructure
7.  **migrate_add_unique_id.py**: Document deduplication support.
8.  **migrate_add_upload_status.py**: Processing status tracking.
9.  **migrate_add_chunk_index_fields.py**: Support for chunk-based indexing.
10. **add_unified_status_fields.py**: Merges status fields for SSE compatibility.
11. **migrate_add_period_end_date.py**: Added period_end_date for calendar synchronicity.
12. **migrate_ticker_uniqueness.py**: Enforced UNIQUE ticker constraint on companies.

#### Analysis & Metrics
13. **migrate_add_ebita_breakdown.py**: Detailed EBITA components.
14. **migrate_add_net_working_capital_breakdown.py**: NWC component tracking.
15. **migrate_add_net_long_term_operating_assets_breakdown.py**: NLTOA component tracking.
16. **migrate_add_adjusted_tax_rate.py** & **breakdown**: Tax rate auditing.
17. **migrate_add_nopat_roic.py**: Advanced profitability metrics.

#### DCF Modeling & Intelligence
18. **migrate_add_financial_assumptions.py**: DCF modeling framework.
19. **add_wacc_and_other_assumptions.py**: Extended DCF parameters (WACC, terminal growth).
20. **add_transformer_columns.py**: AI taxonomy (standardized_name, categories).
21. **add_unique_constraints_manual.py**: Enforced unique constraints for line item ordering.
22. **migrate_v3_shares_gaap_period.py**: Detailed share counts and GAAP period metadata.
23. **remove_nonop_redundant_fields.py**: Schema pruning after taxonomy unification.

---

## Active Incremental Migrations

As of **January 26, 2026**, there are **no active incremental migrations**. All prior feature updates have been successfully merged into the `migrate_baseline_schema.py` logic.

When new schema changes are required:
1.  Create a new script in `migrations/`.
2.  Include both schema modification and any necessary data backfill logic.
3.  Once the change is stable across all environments, it will eventually be archived into the baseline.

---

### Running Migrations

**Fresh Installation / Reset:**
```bash
# This creates all tables and applies all historical logic
python migrate_baseline_schema.py
```

**Checking for Updates:**
If the `migrations/` directory contains new scripts, run them in chronological order.

---

### Why This Approach

1.  **Clean Baseline**: New projects start with a high-performance, validated schema without running 20+ scripts.
2.  **Safety**: Baseline code includes complex backfill logic (e.g., merging duplicate companies or deriving missing file sizes) that simple SQLAlchemy `create_all()` cannot handle.
3.  **Audit Trail**: The `migrations_archive/` maintains history for compliance and troubleshooting.

### Development Workflow

-   **Models are Truth**: Update SQLAlchemy models in `app/models/` first.
-   **Breaking Changes**: If a field is renamed or constraints change, create a new script in `migrations/`.
-   **Archive Cycle**: Periodically, `migrations/` are merged into `migrate_baseline_schema.py` and the scripts moved to `migrations_archive/`.

---

### Schema Overview

The current system manages several key tables:
- **users**: Core authentication (Email/JWT).
- **companies**: Unique entities (Ticker-based).
- **documents**: Universal status tracking and metadata.
- **historical_calculations**: Grouped metrics (EBITA, NOPAT, ROIC).
- **financial_assumptions**: DCF model parameters.
- **organic_growth / shares_outstanding**: Specialized extraction tables.
- **line_items**: Standardized financial data across BS, IS, and GAAP reconciliations.

