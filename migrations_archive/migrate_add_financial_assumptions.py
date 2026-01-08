from app.database import engine
from app.models.financial_assumption import FinancialAssumption


def migrate():
    print("Running migration to create financial_assumptions table...")
    # Create the table
    FinancialAssumption.__table__.create(bind=engine)
    print("Migration completed.")


if __name__ == "__main__":
    migrate()
