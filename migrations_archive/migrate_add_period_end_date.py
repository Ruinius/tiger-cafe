"""
Migration script to add period_end_date column to documents table
"""

from sqlalchemy import text

from app.database import SessionLocal


def migrate():
    """Add period_end_date column to documents table"""
    db = SessionLocal()
    try:
        # Check if column already exists
        result = db.execute(text("PRAGMA table_info(documents)"))
        columns = [row[1] for row in result.fetchall()]

        if "period_end_date" not in columns:
            print("Adding period_end_date column to documents table...")
            db.execute(text("ALTER TABLE documents ADD COLUMN period_end_date VARCHAR"))
            db.commit()
            print("✓ Migration completed successfully")
        else:
            print("✓ Column period_end_date already exists")
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
