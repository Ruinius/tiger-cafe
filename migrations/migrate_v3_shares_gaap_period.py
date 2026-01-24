"""
Migration script to add period_end_date to financial tables and create new shares/gaap tables.
"""

import logging

from sqlalchemy import text

from app.database import Base, SessionLocal, engine
from app.models.gaap_reconciliation import GAAPReconciliation, GAAPReconciliationLineItem
from app.models.shares_outstanding import SharesOutstanding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """
    1. Create new tables if they don't exist
    2. Add period_end_date to existing tables
    """
    # 1. Create new tables
    logger.info("Ensuring new tables exist...")
    Base.metadata.create_all(
        bind=engine,
        tables=[
            SharesOutstanding.__table__,
            GAAPReconciliation.__table__,
            GAAPReconciliationLineItem.__table__,
        ],
    )

    db = SessionLocal()
    try:
        # All tables that should have period fields
        tables_to_update = [
            "income_statements",
            "balance_sheets",
            "historical_calculations",
            "amortizations",
            "organic_growth",
            "non_operating_classifications",
            "other_assets",
            "other_liabilities",
            "financial_metrics",
            "shares_outstanding",
            "gaap_reconciliations",
        ]

        for table in tables_to_update:
            # Check existing columns
            result = db.execute(text(f"PRAGMA table_info({table})"))
            columns = [row[1] for row in result.fetchall()]

            # Ensure time_period exists
            if "time_period" not in columns:
                logger.info(f"Adding time_period column to {table} table...")
                db.execute(text(f"ALTER TABLE {table} ADD COLUMN time_period VARCHAR"))
                db.commit()
                logger.info(f"✓ {table} time_period added")

            # Ensure period_end_date exists
            if "period_end_date" not in columns:
                logger.info(f"Adding period_end_date column to {table} table...")
                db.execute(text(f"ALTER TABLE {table} ADD COLUMN period_end_date VARCHAR"))
                db.commit()
                logger.info(f"✓ {table} period_end_date added")
            else:
                logger.info(f"✓ Columns already exist in {table}")

        logger.info("✓ Migration completed successfully")
    except Exception as e:
        logger.error(f"✗ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
