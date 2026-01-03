"""
Script to clear the database and optionally clean up uploaded files and storage.

Usage:
    python clear_database.py              # Clear database only
    python clear_database.py --files      # Clear database and delete uploaded files
    python clear_database.py --all        # Clear database, files, and storage embeddings
"""

import os
import sys

from sqlalchemy import text

from app.database import SessionLocal, engine
from app.models.company import Company
from app.models.document import Document
from app.models.user import User

# Import all models
try:
    from app.models.analysis_result import AnalysisResult
    from app.models.balance_sheet import BalanceSheet, BalanceSheetLineItem
    from app.models.financial_metric import FinancialMetric
    from app.models.income_statement import IncomeStatement, IncomeStatementLineItem

    HAS_ALL_MODELS = True
except ImportError as e:
    print(f"Warning: Could not import some models: {e}")
    HAS_ALL_MODELS = False
    # Try to import what we can
    try:
        from app.models.analysis_result import AnalysisResult
        from app.models.financial_metric import FinancialMetric
    except ImportError:
        FinancialMetric = None
        AnalysisResult = None
    try:
        from app.models.balance_sheet import BalanceSheet, BalanceSheetLineItem
    except ImportError:
        BalanceSheet = None
        BalanceSheetLineItem = None
    try:
        from app.models.income_statement import IncomeStatement, IncomeStatementLineItem
    except ImportError:
        IncomeStatement = None
        IncomeStatementLineItem = None

from config.config import DATA_STORAGE_DIR, UPLOAD_DIR


def clear_database():
    """Clear all data from the database."""
    db = SessionLocal()
    try:
        print("Clearing database...")

        # Delete in order to respect foreign key constraints
        # Start with child tables that reference documents

        # Delete balance sheet line items first (they reference balance sheets)
        if BalanceSheetLineItem:
            try:
                bs_line_count = db.query(BalanceSheetLineItem).count()
                db.query(BalanceSheetLineItem).delete()
                print(f"  - Deleted {bs_line_count} balance sheet line items")
            except Exception as e:
                print(f"  - Skipped balance sheet line items: {e}")

        # Delete income statement line items first (they reference income statements)
        if IncomeStatementLineItem:
            try:
                is_line_count = db.query(IncomeStatementLineItem).count()
                db.query(IncomeStatementLineItem).delete()
                print(f"  - Deleted {is_line_count} income statement line items")
            except Exception as e:
                print(f"  - Skipped income statement line items: {e}")

        # Delete balance sheets (they reference documents)
        if BalanceSheet:
            try:
                bs_count = db.query(BalanceSheet).count()
                db.query(BalanceSheet).delete()
                print(f"  - Deleted {bs_count} balance sheets")
            except Exception as e:
                print(f"  - Skipped balance sheets: {e}")

        # Delete income statements (they reference documents)
        if IncomeStatement:
            try:
                is_count = db.query(IncomeStatement).count()
                db.query(IncomeStatement).delete()
                print(f"  - Deleted {is_count} income statements")
            except Exception as e:
                print(f"  - Skipped income statements: {e}")

        # Delete financial metrics and analysis results if they exist
        if FinancialMetric:
            try:
                metric_count = db.query(FinancialMetric).count()
                db.query(FinancialMetric).delete()
                print(f"  - Deleted {metric_count} financial metrics")
            except Exception as e:
                print(f"  - Skipped financial metrics: {e}")

        if AnalysisResult:
            try:
                result_count = db.query(AnalysisResult).count()
                db.query(AnalysisResult).delete()
                print(f"  - Deleted {result_count} analysis results")
            except Exception as e:
                print(f"  - Skipped analysis results: {e}")

        # Delete documents (they reference companies and users)
        doc_count = db.query(Document).count()
        db.query(Document).delete()
        print(f"  - Deleted {doc_count} documents")

        # Companies (after documents are deleted)
        company_count = db.query(Company).count()
        db.query(Company).delete()
        print(f"  - Deleted {company_count} companies")

        # Users (after documents are deleted)
        user_count = db.query(User).count()
        db.query(User).delete()
        print(f"  - Deleted {user_count} users")

        # Commit the changes
        db.commit()

        # Reset SQLite sequences if using SQLite
        if "sqlite" in str(engine.url):
            try:
                # SQLite doesn't use sequences, but we can vacuum to reset
                db.execute(text("VACUUM"))
                db.commit()
                print("  - Vacuumed SQLite database")
            except Exception as e:
                print(f"  - Note: Could not vacuum database: {e}")

        print("✓ Database cleared successfully!")

    except Exception as e:
        db.rollback()
        print(f"✗ Error clearing database: {e}")
        raise
    finally:
        db.close()


def clear_uploaded_files():
    """Delete all uploaded PDF files."""
    if not os.path.exists(UPLOAD_DIR):
        print(f"  - Upload directory {UPLOAD_DIR} does not exist")
        return

    try:
        files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith(".pdf")]
        count = len(files)
        for file in files:
            file_path = os.path.join(UPLOAD_DIR, file)
            os.remove(file_path)
        print(f"  - Deleted {count} uploaded PDF files from {UPLOAD_DIR}")
    except Exception as e:
        print(f"  - Error deleting uploaded files: {e}")


def clear_storage_embeddings():
    """Delete all stored embeddings."""
    if not os.path.exists(DATA_STORAGE_DIR):
        print(f"  - Storage directory {DATA_STORAGE_DIR} does not exist")
        return

    try:
        files = [f for f in os.listdir(DATA_STORAGE_DIR) if f.endswith(".json")]
        count = len(files)
        for file in files:
            file_path = os.path.join(DATA_STORAGE_DIR, file)
            os.remove(file_path)
        print(f"  - Deleted {count} embedding files from {DATA_STORAGE_DIR}")
    except Exception as e:
        print(f"  - Error deleting embedding files: {e}")


def main():
    """Main function to clear database and optionally files."""
    clear_files = "--files" in sys.argv or "--all" in sys.argv
    clear_storage = "--all" in sys.argv
    skip_confirm = "--yes" in sys.argv or "-y" in sys.argv

    print("=" * 60)
    print("Tiger-Cafe Database Cleanup Script")
    print("=" * 60)
    print()

    # Show what will be cleared
    actions = ["Database"]
    if clear_files:
        actions.append("Uploaded files")
    if clear_storage:
        actions.append("Storage embeddings")

    print(f"This will clear: {', '.join(actions)}")
    print()

    # Ask for confirmation unless --yes flag is provided
    if not skip_confirm:
        response = input("Are you sure you want to proceed? (yes/no): ").strip().lower()
        if response not in ["yes", "y"]:
            print("Operation cancelled.")
            return
        print()

    # Clear database
    clear_database()
    print()

    # Clear uploaded files if requested
    if clear_files:
        print("Clearing uploaded files...")
        clear_uploaded_files()
        print()

    # Clear storage embeddings if requested
    if clear_storage:
        print("Clearing storage embeddings...")
        clear_storage_embeddings()
        print()

    print("=" * 60)
    print("Cleanup complete!")
    print("=" * 60)
    print()
    print("Usage options:")
    print("  python clear_database.py              # Database only (with confirmation)")
    print("  python clear_database.py --yes       # Skip confirmation prompt")
    print("  python clear_database.py --files     # Database + uploaded files")
    print("  python clear_database.py --all        # Database + files + embeddings")


if __name__ == "__main__":
    main()
