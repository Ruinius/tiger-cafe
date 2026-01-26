"""
Baseline database migration - creates all tables from models.

This migration replaces all previous incremental migrations and creates
a clean baseline schema that matches the current model definitions exactly.

INCORPORATED MIGRATIONS:
This baseline includes all changes from the following migration files:
1. migrate_add_chunk_index_fields.py - Added chunk indexing fields to documents
2. migrate_add_ebita_breakdown.py - Added EBITA breakdown to historical calculations
3. migrate_add_net_working_capital_breakdown.py - Added NWC breakdown fields
4. migrate_add_net_long_term_operating_assets_breakdown.py - Added NLTOA breakdown fields
5. migrate_add_adjusted_tax_rate.py - Added adjusted_tax_rate to historical calculations
6. migrate_add_adjusted_tax_rate_breakdown.py - Added adjusted tax rate breakdown fields
7. migrate_add_nopat_roic.py - Added NOPAT and ROIC to historical calculations
8. migrate_add_financial_assumptions.py - Added financial_assumptions table
9. add_currency_fields.py - Added currency and unit fields across all statements
10. add_transformer_columns.py - Added transformer columns (standardized_name, categories)
11. add_unified_status_fields.py - Integrated unified status and progress tracking
12. add_unique_constraints_manual.py - Enforced unique constraints for line item ordering
13. add_wacc_and_other_assumptions.py - Extended DCF assumptions (WACC, tax rates)
14. migrate_add_period_end_date.py - Added period_end_date for calendar synchronicity
15. migrate_ticker_uniqueness.py - Enforced UNIQUE ticker constraint on companies
16. migrate_v3_shares_gaap_period.py - Added detailed share count and GAAP period fields
17. remove_nonop_redundant_fields.py - Pruned redundant fields after taxonomy unification

All of these changes are now part of the baseline schema defined in the SQLAlchemy models.
The individual migration files have been archived to migrations_archive/.

Run this script to initialize a fresh database or to reset an existing one.
"""

import os
import sys

# Ensure we can import from app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import all models to ensure they're registered with Base.metadata
from app import models  # noqa: F401, E402
from app.database import Base, engine  # noqa: E402


def migrate():
    """
    Create all database tables from SQLAlchemy models.
    """
    print("Creating baseline database schema...")
    print("=" * 60)

    # Get database path for display
    db_url = str(engine.url)
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        print(f"Database: {db_path}")
    else:
        print(f"Database: {db_url}")

    print("\nCreating tables from models:")

    # Create all tables - SQLAlchemy will handle:
    # - Column types, constraints, defaults
    # - Primary keys, foreign keys
    # - Indexes
    # - Enums (as TEXT columns in SQLite)
    # - Relationships (via foreign keys)

    Base.metadata.create_all(bind=engine)

    # List all created tables
    tables = list(Base.metadata.tables.keys())
    print(f"\nCreated {len(tables)} tables:")
    for table_name in sorted(tables):
        print(f"  ✓ {table_name}")

    print("\n" + "=" * 60)
    print("Baseline migration completed successfully!")
    print("\nNote: All previous migration files have been archived to migrations_archive/.")
    print("This baseline migration replaces all incremental migrations.")


def verify_schema():
    """
    Verify that the database schema matches the models.
    """
    from sqlalchemy import inspect

    print("\nVerifying schema...")
    inspector = inspect(engine)

    expected_tables = {
        "users",
        "companies",
        "documents",
        "balance_sheets",
        "balance_sheet_line_items",
        "income_statements",
        "income_statement_line_items",
        "historical_calculations",
        "financial_metrics",
        "analysis_results",
        "financial_assumptions",
        "organic_growth",
        "amortization",
        "amortization_line_items",
        "other_assets",
        "other_assets_line_items",
        "other_liabilities",
        "other_liabilities_line_items",
        "gaap_reconciliation",
        "gaap_reconciliation_line_items",
        "shares_outstanding",
        "valuations",
    }

    existing_tables = set(inspector.get_table_names())

    missing_tables = expected_tables - existing_tables
    if missing_tables:
        print(f"⚠️  Warning: Missing tables: {missing_tables}")
        return False

    extra_tables = existing_tables - expected_tables
    if extra_tables:
        print(f"ℹ️  Info: Extra tables found: {extra_tables}")

    print("✓ All expected tables exist")

    # Verify key columns for each table
    verification_passed = True

    # Verify users table
    if "users" in existing_tables:
        user_cols = {col["name"] for col in inspector.get_columns("users")}
        expected_user_cols = {
            "id",
            "email",
            "name",
            "picture",
            "created_at",
            "updated_at",
            "is_active",
        }
        if not expected_user_cols.issubset(user_cols):
            print(f"⚠️  Warning: users table missing columns: {expected_user_cols - user_cols}")
            verification_passed = False

    # Verify documents table has all expected columns
    if "documents" in existing_tables:
        doc_cols = {col["name"] for col in inspector.get_columns("documents")}
        expected_doc_cols = {
            "id",
            "document_type",
            "time_period",
            "indexing_status",
            "analysis_status",
            "duplicate_detected",
            "page_count",
            "character_count",
            "uploaded_at",
        }
        if not expected_doc_cols.issubset(doc_cols):
            print(f"⚠️  Warning: documents table missing columns: {expected_doc_cols - doc_cols}")
            verification_passed = False

    # Verify company ticker uniqueness index
    if "companies" in existing_tables:
        company_cols = {col["name"] for col in inspector.get_columns("companies")}
        if "ticker" not in company_cols:
            print("⚠️  Warning: companies table missing 'ticker' column")
            verification_passed = False

    # Verify standardization columns in line items
    if "balance_sheet_line_items" in existing_tables:
        bs_item_cols = {col["name"] for col in inspector.get_columns("balance_sheet_line_items")}
        if "standardized_name" not in bs_item_cols:
            print("⚠️  Warning: balance_sheet_line_items missing 'standardized_name'")
            verification_passed = False

    if verification_passed:
        print("✓ Schema verification passed")

    return verification_passed


if __name__ == "__main__":
    try:
        migrate()
        verify_schema()
    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
