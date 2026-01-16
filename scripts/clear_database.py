"""
Script to clear the database and optionally clean up uploaded files and storage.

Usage:
    python clear_database.py              # Clear database only
    python clear_database.py --files      # Clear database and delete uploaded files
    python clear_database.py --all        # Clear database, files, and storage embeddings
"""

import os
import sys

# Add project root to sys.path to allow imports from app
# Add project root to sys.path to allow imports from app
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ensure we run from the project root so that relative paths (database, uploads) work correctly
os.chdir(project_root)

if project_root not in sys.path:
    sys.path.append(project_root)

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal, engine  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.user import User  # noqa: E402
from config.config import DATA_STORAGE_DIR, UPLOAD_DIR  # noqa: E402

# Initialize all model variables to None
AnalysisResult = None
Amortization = None
AmortizationLineItem = None
BalanceSheet = None
BalanceSheetLineItem = None
FinancialAssumption = None
FinancialMetric = None
HistoricalCalculation = None
IncomeStatement = None
IncomeStatementLineItem = None
OrganicGrowth = None
OtherAssets = None
OtherAssetsLineItem = None
OtherLiabilities = None
OtherLiabilitiesLineItem = None
Valuation = None

# Import all models
try:
    from app.models.analysis_result import AnalysisResult
    from app.models.balance_sheet import BalanceSheet, BalanceSheetLineItem
    from app.models.financial_metric import FinancialMetric
    from app.models.income_statement import IncomeStatement, IncomeStatementLineItem

    # New models
    try:
        from app.models.amortization import Amortization, AmortizationLineItem
    except ImportError:
        pass

    try:
        from app.models.financial_assumption import FinancialAssumption
    except ImportError:
        pass

    try:
        from app.models.historical_calculation import HistoricalCalculation
    except ImportError:
        pass

    try:
        from app.models.organic_growth import OrganicGrowth
    except ImportError:
        pass

    try:
        from app.models.other_assets import OtherAssets, OtherAssetsLineItem
    except ImportError:
        pass

    try:
        from app.models.other_liabilities import OtherLiabilities, OtherLiabilitiesLineItem
    except ImportError:
        pass

    try:
        from app.models.valuation import Valuation
    except ImportError:
        pass

except ImportError as e:
    print(f"Warning: Could not import some models: {e}")


def clear_database():
    """Clear all data from the database."""
    db = SessionLocal()
    try:
        print("Clearing database...")

        # Delete in order to respect foreign key constraints

        # 1. DELETE LINE ITEMS (Leaf nodes)
        # =======================================================

        # Balance sheet line items
        if BalanceSheetLineItem:
            try:
                count = db.query(BalanceSheetLineItem).count()
                db.query(BalanceSheetLineItem).delete()
                print(f"  - Deleted {count} balance sheet line items")
            except Exception as e:
                print(f"  - Skipped balance sheet line items: {e}")

        # Income statement line items
        if IncomeStatementLineItem:
            try:
                count = db.query(IncomeStatementLineItem).count()
                db.query(IncomeStatementLineItem).delete()
                print(f"  - Deleted {count} income statement line items")
            except Exception as e:
                print(f"  - Skipped income statement line items: {e}")

        # Amortization line items
        if AmortizationLineItem:
            try:
                count = db.query(AmortizationLineItem).count()
                db.query(AmortizationLineItem).delete()
                print(f"  - Deleted {count} amortization line items")
            except Exception as e:
                print(f"  - Skipped amortization line items: {e}")

        # Other Assets line items
        if OtherAssetsLineItem:
            try:
                count = db.query(OtherAssetsLineItem).count()
                db.query(OtherAssetsLineItem).delete()
                print(f"  - Deleted {count} other assets line items")
            except Exception as e:
                print(f"  - Skipped other assets line items: {e}")

        # Other Liabilities line items
        if OtherLiabilitiesLineItem:
            try:
                count = db.query(OtherLiabilitiesLineItem).count()
                db.query(OtherLiabilitiesLineItem).delete()
                print(f"  - Deleted {count} other liabilities line items")
            except Exception as e:
                print(f"  - Skipped other liabilities line items: {e}")

        # 2. DELETE EXTRACTION RESULTS (Reference Documents)
        # =======================================================

        # Balance sheets
        if BalanceSheet:
            try:
                count = db.query(BalanceSheet).count()
                db.query(BalanceSheet).delete()
                print(f"  - Deleted {count} balance sheets")
            except Exception as e:
                print(f"  - Skipped balance sheets: {e}")

        # Income statements
        if IncomeStatement:
            try:
                count = db.query(IncomeStatement).count()
                db.query(IncomeStatement).delete()
                print(f"  - Deleted {count} income statements")
            except Exception as e:
                print(f"  - Skipped income statements: {e}")

        # Amortization
        if Amortization:
            try:
                count = db.query(Amortization).count()
                db.query(Amortization).delete()
                print(f"  - Deleted {count} amortizations")
            except Exception as e:
                print(f"  - Skipped amortizations: {e}")

        # Other Assets
        if OtherAssets:
            try:
                count = db.query(OtherAssets).count()
                db.query(OtherAssets).delete()
                print(f"  - Deleted {count} other assets")
            except Exception as e:
                print(f"  - Skipped other assets: {e}")

        # Other Liabilities
        if OtherLiabilities:
            try:
                count = db.query(OtherLiabilities).count()
                db.query(OtherLiabilities).delete()
                print(f"  - Deleted {count} other liabilities")
            except Exception as e:
                print(f"  - Skipped other liabilities: {e}")

        # Organic Growth
        if OrganicGrowth:
            try:
                count = db.query(OrganicGrowth).count()
                db.query(OrganicGrowth).delete()
                print(f"  - Deleted {count} organic growth records")
            except Exception as e:
                print(f"  - Skipped organic growth: {e}")

        # Historical Calculations
        if HistoricalCalculation:
            try:
                count = db.query(HistoricalCalculation).count()
                db.query(HistoricalCalculation).delete()
                print(f"  - Deleted {count} historical calculations")
            except Exception as e:
                print(f"  - Skipped historical calculations: {e}")

        # 3. DELETE METRICS & ANALYSES (Reference Companies/Docs)
        # =======================================================

        # Financial metrics
        if FinancialMetric:
            try:
                count = db.query(FinancialMetric).count()
                db.query(FinancialMetric).delete()
                print(f"  - Deleted {count} financial metrics")
            except Exception as e:
                print(f"  - Skipped financial metrics: {e}")

        # Analysis results
        if AnalysisResult:
            try:
                count = db.query(AnalysisResult).count()
                db.query(AnalysisResult).delete()
                print(f"  - Deleted {count} analysis results")
            except Exception as e:
                print(f"  - Skipped analysis results: {e}")

        # Valuations (Reference Company and User)
        if Valuation:
            try:
                count = db.query(Valuation).count()
                db.query(Valuation).delete()
                print(f"  - Deleted {count} valuations")
            except Exception as e:
                print(f"  - Skipped valuations: {e}")

        # Financial Assumptions (Reference Company)
        if FinancialAssumption:
            try:
                count = db.query(FinancialAssumption).count()
                db.query(FinancialAssumption).delete()
                print(f"  - Deleted {count} financial assumptions")
            except Exception as e:
                print(f"  - Skipped financial assumptions: {e}")

        # 4. DELETE DOCUMENTS
        # =======================================================
        doc_count = db.query(Document).count()
        db.query(Document).delete()
        print(f"  - Deleted {doc_count} documents")

        # 5. DELETE COMPANIES & USERS
        # =======================================================

        # Companies (after documents are deleted)
        company_count = db.query(Company).count()
        db.query(Company).delete()
        print(f"  - Deleted {company_count} companies")

        # Users (after documents are deleted)
        user_count = db.query(User).filter(User.email != "dev@example.com").count()
        db.query(User).filter(User.email != "dev@example.com").delete(synchronize_session=False)
        print(f"  - Deleted {user_count} users (Kept dev@example.com)")

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
    # Default to clearing EVERYTHING except dev user
    # Allows --keep-files to skip file deletion
    clear_files = "--keep-files" not in sys.argv
    clear_storage = "--keep-files" not in sys.argv
    skip_confirm = "--yes" in sys.argv or "-y" in sys.argv

    print("=" * 60)
    print("Tiger-Cafe Database Cleanup Script")
    print("=" * 60)
    print()

    # Show what will be cleared
    actions = ["Database (preserving dev user)"]
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
    print("  python clear_database.py              # Clear DB + Files + Storage (Keep dev user)")
    print("  python clear_database.py --keep-files # Clear DB only (Keep dev user & files)")
    print("  python clear_database.py --yes        # Skip confirmation")


if __name__ == "__main__":
    main()
