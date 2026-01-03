# Archived Migrations

These migration files have been replaced by the single baseline migration: `migrate_baseline_schema.py`

## Archived Files

1. **migrate_add_balance_sheet_tables.py** - Created balance_sheets and balance_sheet_line_items tables
2. **migrate_add_income_statement_tables.py** - Created income_statements and income_statement_line_items tables
3. **migrate_add_historical_calculations_table.py** - Created historical_calculations table
4. **migrate_add_unique_id.py** - Added unique_id column to documents table
5. **migrate_add_upload_status.py** - Added upload/processing status fields to documents table
6. **migrate_rename_total_to_basic_shares.py** - Renamed column in income_statements table
7. **migrate_add_unit_fields.py** - Added unit columns to balance_sheets, income_statements, and historical_calculations tables

## Why Archived

All of these incremental migrations have been consolidated into `migrate_baseline_schema.py`, which creates the complete schema from SQLAlchemy models. This ensures:

- **Perfect alignment** between database schema and models
- **Simpler maintenance** with a single migration file
- **Clean baseline** for new installations

## Status

These files are kept for historical reference but should **NOT** be run on new databases. Use `migrate_baseline_schema.py` instead.

