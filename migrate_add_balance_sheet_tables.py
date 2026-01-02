"""
Migration script to add balance sheet tables to the database
"""

from app.database import engine, Base
from app.models.balance_sheet import BalanceSheet, BalanceSheetLineItem

def migrate():
    """
    Create balance sheet tables in the database
    """
    print("Creating balance sheet tables...")
    Base.metadata.create_all(bind=engine, tables=[BalanceSheet.__table__, BalanceSheetLineItem.__table__])
    print("Balance sheet tables created successfully!")

if __name__ == "__main__":
    migrate()


