"""
Migration script to add adjusted_tax_rate to historical_calculations table
"""

import os
import sqlite3

from config.config import DATABASE_URL

db_path = DATABASE_URL.replace("sqlite:///", "")

if not os.path.exists(db_path):
    print(f"Database file not found: {db_path}")
    print("The database will be created automatically on next server start.")
    raise SystemExit(0)

print(f"Connecting to database: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        ALTER TABLE historical_calculations
        ADD COLUMN adjusted_tax_rate REAL
        """
    )

    conn.commit()
    print("adjusted_tax_rate column added successfully.")

except sqlite3.Error as e:
    print(f"Database error: {e}")
finally:
    if conn:
        conn.close()
