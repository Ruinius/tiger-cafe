import os
import sqlite3

# Database path (adjust if different in production)
DB_PATH = "tiger_cafe.db"


def run_migration():
    print(f"Connecting to database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"Error: Database file not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        print("Adding unique index to balance_sheet_line_items...")
        # SQLite constraint naming: usually handled by creating a UNIQUE INDEX
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_bs_line_item_order
            ON balance_sheet_line_items (balance_sheet_id, line_order)
        """)

        print("Adding unique index to income_statement_line_items...")
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_is_line_item_order
            ON income_statement_line_items (income_statement_id, line_order)
        """)

        conn.commit()
        print("Migration completed successfully.")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        if "UNIQUE constraint failed" in str(e):
            print(
                "\nCRITICAL: Duplicate data exists! The unique index could not be created because duplicates were found."
            )
            print(
                "Please run scripts/clear_database.py or manually remove duplicates before retrying."
            )
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    run_migration()
