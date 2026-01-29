import os
import sys

from sqlalchemy import inspect, text

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine


def create_qualitative_assessments_table():
    inspector = inspect(engine)
    if inspector.has_table("qualitative_assessments"):
        print("Table 'qualitative_assessments' already exists.")
        return

    print("Creating 'qualitative_assessments' table...")
    with engine.connect() as conn:
        conn.execute(
            text(
                """
            CREATE TABLE qualitative_assessments (
                id VARCHAR NOT NULL,
                company_id VARCHAR NOT NULL,
                economic_moat_label VARCHAR,
                economic_moat_rationale TEXT,
                near_term_growth_label VARCHAR,
                near_term_growth_rationale TEXT,
                revenue_predictability_label VARCHAR,
                revenue_predictability_rationale TEXT,
                updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
                PRIMARY KEY (id),
                UNIQUE (company_id),
                FOREIGN KEY(company_id) REFERENCES companies (id)
            )
        """
            )
        )
        # SQLite doesn't support creating indexes in the CREATE TABLE statement for some versions/dialects conveniently in raw SQL mixed with SQLAlchemy expectations,
        # so we do it separately or rely on the simple CREATE above.
        # Actually the model definition has indexes.
        # Let's add the index on company_id explicitly to be safe, though UNIQUE constraint usually creates one.

        print("Table created successfully.")


if __name__ == "__main__":
    create_qualitative_assessments_table()
