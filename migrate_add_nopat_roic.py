from sqlalchemy import text

from app.database import engine


def migrate():
    with engine.connect() as conn:
        try:
            # Check if columns exist
            result = conn.execute(text("PRAGMA table_info(historical_calculations)"))
            columns = [row.name for row in result]

            if "nopat" not in columns:
                print("Adding nopat column to historical_calculations table...")
                conn.execute(
                    text("ALTER TABLE historical_calculations ADD COLUMN nopat NUMERIC(20, 2)")
                )
                print("Column nopat added successfully.")

            if "roic" not in columns:
                print("Adding roic column to historical_calculations table...")
                conn.execute(
                    text("ALTER TABLE historical_calculations ADD COLUMN roic NUMERIC(10, 4)")
                )
                print("Column roic added successfully.")

        except Exception as e:
            print(f"Error during migration: {e}")


if __name__ == "__main__":
    migrate()
