"""
Migration script to add upload status tracking fields to documents table.
Run this after updating the Document model.
"""

import os
import sqlite3

from config.config import DATABASE_URL


def migrate():
    # Extract database path from DATABASE_URL
    if DATABASE_URL.startswith("sqlite:///"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
    else:
        db_path = "tiger_cafe.db"

    if not os.path.exists(db_path):
        print(f"Database {db_path} not found. Nothing to migrate.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(documents)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add duplicate_detected column if it doesn't exist
        if "duplicate_detected" not in columns:
            cursor.execute("ALTER TABLE documents ADD COLUMN duplicate_detected BOOLEAN DEFAULT 0")
            print("Added duplicate_detected column")

        # Add existing_document_id column if it doesn't exist
        if "existing_document_id" not in columns:
            cursor.execute("ALTER TABLE documents ADD COLUMN existing_document_id VARCHAR")
            print("Added existing_document_id column")

        conn.commit()
        print("Migration completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"Error during migration: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
