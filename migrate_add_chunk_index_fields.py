"""
Migration script to add chunk_index fields to balance_sheets and income_statements tables
"""

import os
import sqlite3

from config.config import DATABASE_URL

db_path = DATABASE_URL.replace("sqlite:///", "")

if not os.path.exists(db_path):
    print(f"Database file not found: {db_path}")
    print("The database will be created automatically on next server start.")
    exit(0)

print(f"Connecting to database: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Add chunk_index column to balance_sheets table
    try:
        cursor.execute(
            """
            ALTER TABLE balance_sheets
            ADD COLUMN chunk_index INTEGER
        """
        )
        print("Added chunk_index column to balance_sheets table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("chunk_index column already exists in balance_sheets table, skipping...")
        else:
            raise

    # Add chunk_index column to income_statements table
    try:
        cursor.execute(
            """
            ALTER TABLE income_statements
            ADD COLUMN chunk_index INTEGER
        """
        )
        print("Added chunk_index column to income_statements table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("chunk_index column already exists in income_statements table, skipping...")
        else:
            raise

    conn.commit()
    print("Chunk index fields migration completed successfully.")

except sqlite3.Error as e:
    print(f"Database error: {e}")
finally:
    if conn:
        conn.close()
