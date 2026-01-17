import os
import sys

# Ensure we can import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text

from app.database import engine


def migrate():
    """
    Migration script to simplify non_operating_classification_items table.
    Removes redundant fields that are now fetched from balance sheet via join:
    - standardized_name (from balance sheet)
    - line_value (from balance sheet)
    - unit (from balance sheet)
    - is_calculated (from balance sheet)

    Only keeps:
    - line_name (for matching)
    - category (the classification result)
    - source (which table it came from)
    - line_order (display order)
    """
    print("Starting migration: remove_nonop_redundant_fields...")

    with engine.connect() as connection:
        inspector = inspect(engine)

        # Check if table exists
        if "non_operating_classification_items" not in inspector.get_table_names():
            print("  Table non_operating_classification_items does not exist. Skipping migration.")
            return

        # Get current columns
        columns = [
            col["name"] for col in inspector.get_columns("non_operating_classification_items")
        ]
        print(f"  Current columns: {columns}")

        # SQLite doesn't support DROP COLUMN, so we need to recreate the table
        print("  Creating new table with simplified schema...")
        connection.execute(
            text("""
            CREATE TABLE non_operating_classification_items_new (
                id TEXT PRIMARY KEY,
                classification_id TEXT NOT NULL,
                line_name TEXT NOT NULL,
                category TEXT,
                source TEXT,
                line_order INTEGER NOT NULL,
                FOREIGN KEY (classification_id) REFERENCES non_operating_classifications(id)
            )
        """)
        )

        print("  Copying data to new table...")
        connection.execute(
            text("""
            INSERT INTO non_operating_classification_items_new
                (id, classification_id, line_name, category, source, line_order)
            SELECT id, classification_id, line_name, category, source, line_order
            FROM non_operating_classification_items
        """)
        )

        print("  Dropping old table...")
        connection.execute(text("DROP TABLE non_operating_classification_items"))

        print("  Renaming new table...")
        connection.execute(
            text("""
            ALTER TABLE non_operating_classification_items_new
            RENAME TO non_operating_classification_items
        """)
        )

        print("  Creating index...")
        connection.execute(
            text("""
            CREATE INDEX ix_non_operating_classification_items_classification_id
            ON non_operating_classification_items(classification_id)
        """)
        )

        connection.commit()

    print("Migration completed successfully.")
    print("  Removed columns: standardized_name, line_value, unit, is_calculated")
    print("  These fields will now be fetched from the balance sheet via a join")


if __name__ == "__main__":
    migrate()
