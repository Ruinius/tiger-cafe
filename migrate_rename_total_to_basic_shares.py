"""
Migration script to rename total_shares_outstanding to basic_shares_outstanding
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

    # Check if the column exists
    cursor.execute("PRAGMA table_info(income_statements)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'total_shares_outstanding' in columns and 'basic_shares_outstanding' not in columns:
        # SQLite doesn't support ALTER TABLE RENAME COLUMN directly in older versions
        # We need to recreate the table
        print("Renaming total_shares_outstanding to basic_shares_outstanding...")
        
        # Create new table with correct column name
        cursor.execute("""
            CREATE TABLE income_statements_new (
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
        
        # Copy data from old table to new table
        cursor.execute("""
            INSERT INTO income_statements_new 
            SELECT 
                id,
                document_id,
                time_period,
                currency,
                extraction_date,
                revenue_prior_year,
                revenue_growth_yoy,
                total_shares_outstanding,
                diluted_shares_outstanding,
                amortization,
                is_valid,
                validation_errors
            FROM income_statements
        """)
        
        # Drop old table
        cursor.execute("DROP TABLE income_statements")
        
        # Rename new table
        cursor.execute("ALTER TABLE income_statements_new RENAME TO income_statements")
        
        # Recreate indexes
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_income_statements_document_id ON income_statements (document_id)")
        
        conn.commit()
        print("Successfully renamed total_shares_outstanding to basic_shares_outstanding.")
    elif 'basic_shares_outstanding' in columns:
        print("Column basic_shares_outstanding already exists. No migration needed.")
    else:
        print("Column total_shares_outstanding not found. Table may not exist yet.")

except sqlite3.Error as e:
    print(f"Database error: {e}")
    conn.rollback()
finally:
    if conn:
        conn.close()

