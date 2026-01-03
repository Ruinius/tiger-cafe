"""
Migration script to add income statement tables to the database
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

    # Add income_statements table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS income_statements (
            id TEXT PRIMARY KEY,
            document_id TEXT UNIQUE NOT NULL,
            time_period TEXT,
            currency TEXT,
            extraction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            revenue_prior_year REAL,
            revenue_growth_yoy REAL,
            basic_shares_outstanding REAL,
            diluted_shares_outstanding REAL,
            amortization REAL,
            is_valid BOOLEAN DEFAULT FALSE,
            validation_errors TEXT,
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
        )
    """)

    # Add income_statement_line_items table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS income_statement_line_items (
            id TEXT PRIMARY KEY,
            income_statement_id TEXT NOT NULL,
            line_name TEXT NOT NULL,
            line_value REAL NOT NULL,
            line_category TEXT,
            is_operating BOOLEAN,
            line_order INTEGER NOT NULL,
            FOREIGN KEY (income_statement_id) REFERENCES income_statements (id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    print("Income statement tables migrated successfully.")

except sqlite3.Error as e:
    print(f"Database error: {e}")
finally:
    if conn:
        conn.close()

