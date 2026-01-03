"""
Baseline database migration - creates all tables from models.

This migration replaces all previous incremental migrations and creates
a clean baseline schema that matches the current model definitions exactly.

Run this script to initialize a fresh database or to reset an existing one.
"""

import os
import sys

# Ensure we can import from app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import Base, engine

# Import all models to ensure they're registered with Base.metadata


def migrate():
    """
    Create all database tables from SQLAlchemy models.

    This creates:
    - users
    - companies
    - documents
    - balance_sheets
    - balance_sheet_line_items
    - income_statements
    - income_statement_line_items
    - historical_calculations
    - financial_metrics
    - analysis_results
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
    print("\nNote: All previous migration files can now be archived.")
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
    }

    existing_tables = set(inspector.get_table_names())

    missing_tables = expected_tables - existing_tables
    if missing_tables:
        print(f"⚠️  Warning: Missing tables: {missing_tables}")
        return False

    extra_tables = existing_tables - expected_tables
    if extra_tables:
        print(f"ℹ️  Info: Extra tables found (may be from other migrations): {extra_tables}")

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
            "user_id",
            "company_id",
            "filename",
            "file_path",
            "document_type",
            "time_period",
            "unique_id",
            "indexing_status",
            "analysis_status",
            "duplicate_detected",
            "existing_document_id",
            "summary",
            "page_count",
            "character_count",
            "uploaded_at",
            "indexed_at",
            "processed_at",
        }
        if not expected_doc_cols.issubset(doc_cols):
            print(f"⚠️  Warning: documents table missing columns: {expected_doc_cols - doc_cols}")
            verification_passed = False

    # Verify balance_sheets has unit column
    if "balance_sheets" in existing_tables:
        bs_cols = {col["name"] for col in inspector.get_columns("balance_sheets")}
        if "unit" not in bs_cols:
            print("⚠️  Warning: balance_sheets table missing 'unit' column")
            verification_passed = False

    # Verify income_statements has all unit columns
    if "income_statements" in existing_tables:
        is_cols = {col["name"] for col in inspector.get_columns("income_statements")}
        expected_unit_cols = {
            "unit",
            "revenue_prior_year_unit",
            "basic_shares_outstanding_unit",
            "diluted_shares_outstanding_unit",
            "amortization_unit",
        }
        missing_unit_cols = expected_unit_cols - is_cols
        if missing_unit_cols:
            print(f"⚠️  Warning: income_statements table missing unit columns: {missing_unit_cols}")
            verification_passed = False

    # Verify historical_calculations has unit column
    if "historical_calculations" in existing_tables:
        hc_cols = {col["name"] for col in inspector.get_columns("historical_calculations")}
        if "unit" not in hc_cols:
            print("⚠️  Warning: historical_calculations table missing 'unit' column")
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
