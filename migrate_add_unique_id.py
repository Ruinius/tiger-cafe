"""
Migration script to add unique_id column to documents table
Run this once to update your existing database schema.
"""

import sqlite3
import os
from config.config import DATABASE_URL

# Extract database path from SQLite URL
db_path = DATABASE_URL.replace("sqlite:///", "")

if not os.path.exists(db_path):
    print(f"Database file not found: {db_path}")
    print("The database will be created automatically on next server start.")
    exit(0)

print(f"Connecting to database: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if column already exists
    cursor.execute("PRAGMA table_info(documents)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'unique_id' in columns:
        print("Column 'unique_id' already exists. No migration needed.")
    else:
        print("Adding 'unique_id' column to documents table...")
        cursor.execute("ALTER TABLE documents ADD COLUMN unique_id TEXT")
        conn.commit()
        print("✅ Migration completed successfully!")
        print("The 'unique_id' column has been added to the documents table.")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error during migration: {str(e)}")
    exit(1)

