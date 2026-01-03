"""
Migration script to add historical_calculations table to the database
"""

import sqlite3
import os
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

    # Add historical_calculations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historical_calculations (
            id TEXT PRIMARY KEY,
            document_id TEXT UNIQUE NOT NULL,
            time_period TEXT,
            currency TEXT,
            calculated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            net_working_capital REAL,
            net_long_term_operating_assets REAL,
            invested_capital REAL,
            capital_turnover REAL,
            ebita REAL,
            ebita_margin REAL,
            effective_tax_rate REAL,
            calculation_notes TEXT,
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    print("Historical calculations table migrated successfully.")

except sqlite3.Error as e:
    print(f"Database error: {e}")
finally:
    if conn:
        conn.close()

