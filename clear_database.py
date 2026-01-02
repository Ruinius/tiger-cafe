"""
Script to clear the database and optionally clean up uploaded files and storage.

Usage:
    python clear_database.py              # Clear database only
    python clear_database.py --files      # Clear database and delete uploaded files
    python clear_database.py --all        # Clear database, files, and storage embeddings
"""

import sys
import os
import shutil
from sqlalchemy import text
from app.database import SessionLocal, engine
from app.models.document import Document
from app.models.company import Company
from app.models.user import User

# Try to import other models if they exist
try:
    from app.models.financial_metric import FinancialMetric
    from app.models.analysis_result import AnalysisResult
    HAS_OTHER_MODELS = True
except ImportError:
    HAS_OTHER_MODELS = False

from config.config import UPLOAD_DIR, DATA_STORAGE_DIR


def clear_database():
    """Clear all data from the database."""
    db = SessionLocal()
    try:
        print("Clearing database...")
        
        # Delete in order to respect foreign key constraints
        # Documents first (they reference companies and users)
        doc_count = db.query(Document).count()
        db.query(Document).delete()
        print(f"  - Deleted {doc_count} documents")
        
        # Delete financial metrics and analysis results if they exist
        if HAS_OTHER_MODELS:
            try:
                metric_count = db.query(FinancialMetric).count()
                db.query(FinancialMetric).delete()
                print(f"  - Deleted {metric_count} financial metrics")
            except Exception as e:
                print(f"  - Skipped financial metrics: {e}")
            
            try:
                result_count = db.query(AnalysisResult).count()
                db.query(AnalysisResult).delete()
                print(f"  - Deleted {result_count} analysis results")
            except Exception as e:
                print(f"  - Skipped analysis results: {e}")
        
        # Companies (after documents are deleted due to cascade)
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
        files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith('.pdf')]
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
        files = [f for f in os.listdir(DATA_STORAGE_DIR) if f.endswith('.json')]
        count = len(files)
        for file in files:
            file_path = os.path.join(DATA_STORAGE_DIR, file)
            os.remove(file_path)
        print(f"  - Deleted {count} embedding files from {DATA_STORAGE_DIR}")
    except Exception as e:
        print(f"  - Error deleting embedding files: {e}")


def main():
    """Main function to clear database and optionally files."""
    clear_files = '--files' in sys.argv or '--all' in sys.argv
    clear_storage = '--all' in sys.argv
    
    print("=" * 60)
    print("Tiger-Cafe Database Cleanup Script")
    print("=" * 60)
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
    print("  python clear_database.py              # Database only")
    print("  python clear_database.py --files       # Database + uploaded files")
    print("  python clear_database.py --all         # Database + files + embeddings")


if __name__ == "__main__":
    main()


