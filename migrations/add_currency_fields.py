import os
import sys

# Add root directory to python path
sys.path.append(os.getcwd())

from sqlalchemy import create_engine, text

from app.database import DATABASE_URL


def migrate():
    print(f"Connecting to database: {DATABASE_URL}")
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
    )
    with engine.connect() as conn:
        print("Checking for new columns in financial_assumptions...")

        # Check if columns exist
        try:
            conn.execute(text("SELECT currency_conversion_rate FROM financial_assumptions LIMIT 1"))
            print("currency_conversion_rate column exists.")
        except Exception:
            print("Adding currency_conversion_rate column...")
            conn.execute(
                text(
                    "ALTER TABLE financial_assumptions ADD COLUMN currency_conversion_rate NUMERIC(10, 4)"
                )
            )

        try:
            conn.execute(text("SELECT adr_conversion_factor FROM financial_assumptions LIMIT 1"))
            print("adr_conversion_factor column exists.")
        except Exception:
            print("Adding adr_conversion_factor column...")
            conn.execute(
                text(
                    "ALTER TABLE financial_assumptions ADD COLUMN adr_conversion_factor NUMERIC(10, 4)"
                )
            )

        conn.commit()
        print("Migration complete.")


if __name__ == "__main__":
    migrate()
