# Database Migration Guide

## Baseline Migration

All incremental database migrations have been consolidated into a single baseline migration: `migrate_baseline_schema.py`.

### What Changed

**Before:** Multiple incremental migration files:
- `migrate_add_balance_sheet_tables.py`
- `migrate_add_income_statement_tables.py`
- `migrate_add_historical_calculations_table.py`
- `migrate_add_unique_id.py`
- `migrate_add_upload_status.py`
- `migrate_rename_total_to_basic_shares.py`
- `migrate_add_unit_fields.py`

**After:** Single baseline migration:
- `migrate_baseline_schema.py` - Creates all tables from SQLAlchemy models

### Why This Approach

1. **Schema-Model Alignment**: The baseline migration uses SQLAlchemy's `Base.metadata.create_all()` which ensures the database schema exactly matches the model definitions.

2. **Simpler Maintenance**: One file to maintain instead of multiple incremental migrations.

3. **Clean State**: For new installations or when resetting the database, you get a clean, consistent schema.

### Running the Baseline Migration

**Automatic Schema Creation:**
The schema is automatically created from models when the application starts (`app/main.py`). For most development scenarios, no manual migration is needed.

**Manual Migration (if needed):**
```bash
# Using conda Python
.conda/python.exe migrate_baseline_schema.py

# Or if Python is in PATH
python migrate_baseline_schema.py

# Or using uv
uv run python migrate_baseline_schema.py
```

The migration will:
1. Create all tables from the models
2. Set up all indexes, foreign keys, and constraints
3. Verify the schema matches the models

### Schema Verification

The migration script includes a verification step that checks:
- All expected tables exist
- Key columns are present (including unit fields)
- Schema matches model definitions

### Old Migration Files

The old migration files have been archived in `migrations_archive/` for historical reference. These should **NOT** be run on new databases - use `migrate_baseline_schema.py` instead.

### Development vs Production Workflow

**Development (Current):**
- Schema automatically created from models on app startup
- Models are the single source of truth
- Baseline migration available for manual initialization/reset

**Future Production:**
- Run `migrate_baseline_schema.py` once to create initial schema
- For schema changes, create new incremental migrations
- Migration chain: `baseline → migration_1 → migration_2 → ...`

### For Existing Databases

If you have an existing database and want to reset it:

1. **Backup your data first!**
2. Delete or rename the existing database file: `tiger_cafe.db`
3. Run the baseline migration: `python migrate_baseline_schema.py`

### Schema Overview

The baseline migration creates these tables:

1. **users** - User authentication and profiles
2. **companies** - Company information
3. **documents** - Document metadata and processing status
4. **balance_sheets** - Balance sheet data
5. **balance_sheet_line_items** - Individual balance sheet line items
6. **income_statements** - Income statement data
7. **income_statement_line_items** - Individual income statement line items
8. **historical_calculations** - Calculated financial metrics
9. **financial_metrics** - Company financial metrics
10. **analysis_results** - Analysis and valuation results

All tables are created with:
- Proper foreign key relationships
- Indexes for performance
- Constraints (unique, nullable, defaults)
- Unit fields for financial data (ones, thousands, millions, billions, ten_thousands)

### Model-Schema Alignment

The baseline migration ensures perfect alignment by:
- Directly using SQLAlchemy model definitions
- Automatically handling column types, constraints, and relationships
- Creating indexes based on model definitions
- Supporting SQLite-specific features (TEXT for enums, etc.)

