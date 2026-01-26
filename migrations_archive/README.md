# Archived Migration Files

This directory contains historical migration files that have been **incorporated into the baseline schema**.

## Status: ARCHIVED - DO NOT RUN

These migration files are kept for historical reference only. All changes from these migrations are now part of the baseline schema defined in `migrate_baseline_schema.py` and the SQLAlchemy models.

## Archived Migrations

### Original Baseline Migrations
1. **migrate_add_balance_sheet_tables.py** - Created balance_sheets and balance_sheet_line_items tables
2. **migrate_add_income_statement_tables.py** - Created income_statements and income_statement_line_items tables
3. **migrate_add_historical_calculations_table.py** - Created historical_calculations table
4. **migrate_add_unique_id.py** - Added unique_id column to documents table
5. **migrate_add_upload_status.py** - Added upload/processing status fields to documents table
6. **migrate_rename_total_to_basic_shares.py** - Renamed column in income_statements table
7. **migrate_add_unit_fields.py** - Added unit columns to balance_sheets, income_statements, and historical_calculations tables

### Additional Feature Migrations (Archived 2026-01-08)
8. **migrate_add_chunk_index_fields.py** - Added chunk indexing fields to documents table
9. **migrate_add_ebita_breakdown.py** - Added EBITA breakdown to historical_calculations table
10. **migrate_add_net_working_capital_breakdown.py** - Added Net Working Capital breakdown fields
11. **migrate_add_net_long_term_operating_assets_breakdown.py** - Added Net Long Term Operating Assets breakdown fields
12. **migrate_add_adjusted_tax_rate.py** - Added adjusted_tax_rate to historical_calculations table
13. **migrate_add_adjusted_tax_rate_breakdown.py** - Added adjusted tax rate breakdown fields
14. **migrate_add_nopat_roic.py** - Added NOPAT and ROIC to historical_calculations table
15. **migrate_add_financial_assumptions.py** - Added financial_assumptions table for DCF modeling

### Intelligence & Taxonomy Migrations (Archived 2026-01-26)
16. **add_currency_fields.py** - Added currency and unit fields across all statements
17. **add_transformer_columns.py** - Added transformer columns (standardized_name, categories)
18. **add_unified_status_fields.py** - Integrated unified status and progress tracking
19. **add_unique_constraints_manual.py** - Enforced unique constraints for line item ordering
20. **add_wacc_and_other_assumptions.py** - Extended DCF assumptions (WACC, tax rates)
21. **migrate_add_period_end_date.py** - Added period_end_date for calendar synchronicity
22. **migrate_ticker_uniqueness.py** - Enforced UNIQUE ticker constraint on companies
23. **migrate_v3_shares_gaap_period.py** - Added detailed share count and GAAP period fields
24. **remove_nonop_redundant_fields.py** - Pruned redundant fields after taxonomy unification

## Why Archived

All of these incremental migrations have been consolidated into `migrate_baseline_schema.py`, which creates the complete schema from SQLAlchemy models. This ensures:

- **Perfect alignment** between database schema and models
- **Simpler maintenance** with a single migration file
- **Clean baseline** for new installations
- **All features included** from day one

## For New Databases

Use `migrate_baseline_schema.py` in the root directory to create a fresh database with all these changes already included.

## For Existing Databases

If you have an existing database that was created with these incremental migrations, it should already have all these fields. The baseline migration is equivalent to running all these migrations in sequence.

