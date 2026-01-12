# Database Migration Guide

## Baseline Migration

All major historical migrations have been consolidated into a single baseline migration: `migrate_baseline_schema.py`. This script initializes a fresh database with the complete schema current as of January 2026.

### Incorporated Migrations (Archived)

The following historical migrations are now part of the baseline schema and are moved to `migrations_archive/`:

1.  **migrate_add_balance_sheet_tables.py**: Foundation for BS data.
2.  **migrate_add_income_statement_tables.py**: Foundation for IS data.
3.  **migrate_add_historical_calculations_table.py**: Foundation for analysis metrics.
4.  **migrate_add_unique_id.py**: Document deduplication support.
5.  **migrate_add_upload_status.py**: Processing status tracking.
6.  **migrate_add_unit_fields.py**: Unit handling (thousands, millions, etc.).
7.  **migrate_add_chunk_index_fields.py**: Support for chunk-based indexing.
8.  **migrate_add_financial_assumptions.py**: DCF modeling framework.
9.  **migrate_add_nopat_roic.py**: Advanced profitability metrics.

---

## Active Incremental Migrations

For users with an existing database, the following **active** migrations must be run sequentially from the `migrations/` directory. These reflect the most recent feature updates and stability improvements.

### 1. Unified Status Fields (`migrations/add_unified_status_fields.py`)
- **Purpose**: Merges `indexing_status` and `analysis_status` into a single `status` column for better compatibility with Server-Sent Events (SSE).
- **Changes**: Adds `status`, `file_size`, `error_message`, `processing_metadata`, and `current_step` to the `documents` table.

### 2. Ticker Uniqueness (`migrations/migrate_ticker_uniqueness.py`)
- **Purpose**: Enforces distinct tickers for companies to prevent data fragmentation.
- **Changes**: Merges duplicate records by ticker and updates all foreign key relationships before applying a `UNIQUE` constraint.

### 3. Period End Date (`migrations/migrate_add_period_end_date.py`)
- **Purpose**: Adds a standardized date field for documents to improve sorting and chronological analysis.
- **Changes**: Adds `period_end_date` to the `documents` table.

---

### Running Migrations

**Fresh Installation:**
```bash
# Simply run the baseline script
python migrate_baseline_schema.py
```

**Existing Database (Incremental):**
```bash
# Run newest migrations sequentially
python migrations/add_unified_status_fields.py
python migrations/migrate_ticker_uniqueness.py
python migrations/migrate_add_period_end_date.py
```

---

### Why This Approach

1.  **Clean Baseline**: New projects start with a high-performance, validated schema.
2.  **Safety**: Active migrations include backfill logic (e.g., merging duplicates or deriving file sizes) that `create_all()` cannot handle.
3.  **Audit Trail**: The `migrations_archive/` maintains history for compliance and troubleshooting.

### Development Workflow

-   **Models are Truth**: Update SQLAlchemy models in `app/models/` first.
-   **Local Dev**: App automatically attempts to create missing tables on startup.
-   **Breaking Changes**: If a field is renamed or constraints change, create a new script in `migrations/`.

---

### Schema Overview

The current system manages several key tables:
- **users**: Core authentication (Email/JWT).
- **companies**: Unique entities (Ticker-based).
- **documents**: Universal status tracking and metadata.
- **historical_calculations**: Grouped metrics (EBITA, NOPAT, ROIC).
- **valuations**: Historical snapshots of fair value estimates.

