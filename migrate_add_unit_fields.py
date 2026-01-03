"""
Migration script to add unit fields to balance_sheets, income_statements, and historical_calculations tables
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

    # Add unit column to balance_sheets table
    try:
        cursor.execute("""
            ALTER TABLE balance_sheets 
            ADD COLUMN unit TEXT
        """)
        print("Added unit column to balance_sheets table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("unit column already exists in balance_sheets table, skipping...")
        else:
            raise

    # Add unit column to income_statements table
    try:
        cursor.execute("""
            ALTER TABLE income_statements 
            ADD COLUMN unit TEXT
        """)
        print("Added unit column to income_statements table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("unit column already exists in income_statements table, skipping...")
        else:
            raise

    # Add unit fields to income_statements table for additional items
    try:
        cursor.execute("""
            ALTER TABLE income_statements 
            ADD COLUMN revenue_prior_year_unit TEXT
        """)
        print("Added revenue_prior_year_unit column to income_statements table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("revenue_prior_year_unit column already exists in income_statements table, skipping...")
        else:
            raise

    try:
        cursor.execute("""
            ALTER TABLE income_statements 
            ADD COLUMN basic_shares_outstanding_unit TEXT
        """)
        print("Added basic_shares_outstanding_unit column to income_statements table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("basic_shares_outstanding_unit column already exists in income_statements table, skipping...")
        else:
            raise

    try:
        cursor.execute("""
            ALTER TABLE income_statements 
            ADD COLUMN diluted_shares_outstanding_unit TEXT
        """)
        print("Added diluted_shares_outstanding_unit column to income_statements table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("diluted_shares_outstanding_unit column already exists in income_statements table, skipping...")
        else:
            raise

    try:
        cursor.execute("""
            ALTER TABLE income_statements 
            ADD COLUMN amortization_unit TEXT
        """)
        print("Added amortization_unit column to income_statements table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("amortization_unit column already exists in income_statements table, skipping...")
        else:
            raise

    # Add unit column to historical_calculations table
    try:
        cursor.execute("""
            ALTER TABLE historical_calculations 
            ADD COLUMN unit TEXT
        """)
        print("Added unit column to historical_calculations table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("unit column already exists in historical_calculations table, skipping...")
        else:
            raise

    conn.commit()
    print("Unit fields migration completed successfully.")

except sqlite3.Error as e:
    print(f"Database error: {e}")
finally:
    if conn:
        conn.close()

