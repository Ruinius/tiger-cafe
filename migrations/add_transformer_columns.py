import os
import sys

# Ensure we can import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text

from app.database import engine


def migrate():
    """
    Migration script to add tiger-transformer support columns:
    1. Add 'standardized_name' and 'is_calculated' to balance_sheet_line_items
    2. Add 'standardized_name', 'is_calculated', and 'is_expense' to income_statement_line_items
    """
    print("Starting migration: add_transformer_columns...")

    with engine.connect() as connection:
        # Check existing columns using Inspector
        inspector = inspect(engine)

        # 1. Balance Sheet Line Items
        print("Checking/Adding columns to balance_sheet_line_items...")
        bs_columns = [col["name"] for col in inspector.get_columns("balance_sheet_line_items")]

        if "standardized_name" not in bs_columns:
            print("  Adding 'standardized_name' column to balance_sheet_line_items...")
            connection.execute(
                text("ALTER TABLE balance_sheet_line_items ADD COLUMN standardized_name VARCHAR")
            )

        if "is_calculated" not in bs_columns:
            print("  Adding 'is_calculated' column to balance_sheet_line_items...")
            connection.execute(
                text("ALTER TABLE balance_sheet_line_items ADD COLUMN is_calculated BOOLEAN")
            )

        # 2. Income Statement Line Items
        print("Checking/Adding columns to income_statement_line_items...")
        is_columns = [col["name"] for col in inspector.get_columns("income_statement_line_items")]

        if "standardized_name" not in is_columns:
            print("  Adding 'standardized_name' column to income_statement_line_items...")
            connection.execute(
                text("ALTER TABLE income_statement_line_items ADD COLUMN standardized_name VARCHAR")
            )

        if "is_calculated" not in is_columns:
            print("  Adding 'is_calculated' column to income_statement_line_items...")
            connection.execute(
                text("ALTER TABLE income_statement_line_items ADD COLUMN is_calculated BOOLEAN")
            )

        if "is_expense" not in is_columns:
            print("  Adding 'is_expense' column to income_statement_line_items...")
            connection.execute(
                text("ALTER TABLE income_statement_line_items ADD COLUMN is_expense BOOLEAN")
            )

        connection.commit()

    print("Migration completed successfully.")


if __name__ == "__main__":
    migrate()
