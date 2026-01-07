"""
Migration script to add net_long_term_operating_assets_breakdown column to historical_calculations table
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

    # Add net_long_term_operating_assets_breakdown column to historical_calculations table
    try:
        cursor.execute(
            """
            ALTER TABLE historical_calculations
            ADD COLUMN net_long_term_operating_assets_breakdown TEXT
        """
        )
        print(
            "Added net_long_term_operating_assets_breakdown column to historical_calculations table."
        )
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print(
                "net_long_term_operating_assets_breakdown column already exists in historical_calculations table, skipping..."
            )
        else:
            raise

    conn.commit()
    print("Net long term operating assets breakdown migration completed successfully.")

except sqlite3.Error as e:
    print(f"Database error: {e}")
finally:
    if conn:
        conn.close()
