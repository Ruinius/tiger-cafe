"""
Migration script to add beta, diluted_shares_outstanding, and base_revenue columns to financial_assumptions table
"""

from sqlalchemy import text

from app.database import SessionLocal


def migrate():
    """Add beta, diluted_shares_outstanding, and base_revenue columns to financial_assumptions table"""
    db = SessionLocal()
    try:
        # Check which columns already exist
        result = db.execute(text("PRAGMA table_info(financial_assumptions)"))
        columns = [row[1] for row in result.fetchall()]

        changes_made = False

        if "beta" not in columns:
            print("Adding beta column to financial_assumptions table...")
            db.execute(text("ALTER TABLE financial_assumptions ADD COLUMN beta NUMERIC(10, 4)"))
            changes_made = True
        else:
            print("✓ Column beta already exists")

        if "diluted_shares_outstanding" not in columns:
            print("Adding diluted_shares_outstanding column to financial_assumptions table...")
            db.execute(
                text(
                    "ALTER TABLE financial_assumptions ADD COLUMN diluted_shares_outstanding NUMERIC(20, 2)"
                )
            )
            changes_made = True
        else:
            print("✓ Column diluted_shares_outstanding already exists")

        if "base_revenue" not in columns:
            print("Adding base_revenue column to financial_assumptions table...")
            db.execute(
                text("ALTER TABLE financial_assumptions ADD COLUMN base_revenue NUMERIC(20, 2)")
            )
            changes_made = True
        else:
            print("✓ Column base_revenue already exists")

        if changes_made:
            db.commit()
            print("✓ Migration completed successfully")
        else:
            print("✓ All columns already exist, no changes needed")
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
