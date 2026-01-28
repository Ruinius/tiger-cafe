import os
import sys

from sqlalchemy import inspect, text

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine


def add_document_date_column():
    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("documents")]

    if "document_date" in columns:
        print("Column 'document_date' already exists in 'documents' table.")
        return

    print("Adding 'document_date' column to 'documents' table...")
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE documents ADD COLUMN document_date VARCHAR"))
        print("Column added successfully.")


if __name__ == "__main__":
    add_document_date_column()
