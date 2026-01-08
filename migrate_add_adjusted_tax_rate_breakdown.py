from sqlalchemy import text

from app.database import engine


def migrate():
    with engine.connect() as conn:
        try:
            # Check if column exists
            result = conn.execute(text("PRAGMA table_info(historical_calculations)"))
            columns = [row.name for row in result]

            if "adjusted_tax_rate_breakdown" not in columns:
                print(
                    "Adding adjusted_tax_rate_breakdown column to historical_calculations table..."
                )
                conn.execute(
                    text(
                        "ALTER TABLE historical_calculations ADD COLUMN adjusted_tax_rate_breakdown TEXT"
                    )
                )
                print("Column added successfully.")
            else:
                print("Column adjusted_tax_rate_breakdown already exists.")

        except Exception as e:
            print(f"Error during migration: {e}")


if __name__ == "__main__":
    migrate()
