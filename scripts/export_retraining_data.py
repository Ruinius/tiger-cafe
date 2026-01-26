"""
Export financial statement data for tiger-transformer retraining.

This script exports balance sheet and income statement line items for a specific company
in the format required for retraining the tiger-transformer model.

Output format:
- File Name: {TICKER}_{BS|IS}_{PERIOD}.csv (e.g., ADBE_BS_Q42025.csv)
- Columns: row_name, section, is_calculated, standardized_name, company
- Output folder: data/tiger-transformer_add_data/
"""

import argparse
import csv
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.balance_sheet import BalanceSheet, BalanceSheetLineItem  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.income_statement import IncomeStatement, IncomeStatementLineItem  # noqa: E402


def export_balance_sheet(
    db: Session, company_ticker: str, time_period: str, output_dir: Path
) -> None:
    """Export balance sheet line items for a company and period."""
    # Find company
    company = db.query(Company).filter(Company.ticker == company_ticker).first()
    if not company:
        print(f"Company with ticker '{company_ticker}' not found")
        return

    # Find balance sheet
    balance_sheet = (
        db.query(BalanceSheet)
        .filter(
            BalanceSheet.company_id == company.id,
            BalanceSheet.time_period == time_period,
        )
        .first()
    )

    if not balance_sheet:
        print(f"Balance sheet for {company_ticker} {time_period} not found")
        return

    # Get line items
    line_items = (
        db.query(BalanceSheetLineItem)
        .filter(BalanceSheetLineItem.balance_sheet_id == balance_sheet.id)
        .order_by(BalanceSheetLineItem.line_order)
        .all()
    )

    if not line_items:
        print(f"No line items found for {company_ticker} {time_period} balance sheet")
        return

    # Create output file
    period_clean = time_period.replace(" ", "")
    output_file = output_dir / f"{company_ticker}_BS_{period_clean}.csv"

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["row_name", "section", "is_calculated", "standardized_name", "company"])

        for item in line_items:
            writer.writerow(
                [
                    item.line_name,
                    item.line_category or "",
                    item.is_calculated if item.is_calculated is not None else "",
                    item.standardized_name or "",
                    company.name,
                ]
            )

    print(f"✓ Exported balance sheet to {output_file}")
    print(f"  {len(line_items)} line items")


def export_income_statement(
    db: Session, company_ticker: str, time_period: str, output_dir: Path
) -> None:
    """Export income statement line items for a company and period."""
    # Find company
    company = db.query(Company).filter(Company.ticker == company_ticker).first()
    if not company:
        print(f"Company with ticker '{company_ticker}' not found")
        return

    # Find income statement
    income_statement = (
        db.query(IncomeStatement)
        .filter(
            IncomeStatement.company_id == company.id,
            IncomeStatement.time_period == time_period,
        )
        .first()
    )

    if not income_statement:
        print(f"Income statement for {company_ticker} {time_period} not found")
        return

    # Get line items
    line_items = (
        db.query(IncomeStatementLineItem)
        .filter(IncomeStatementLineItem.income_statement_id == income_statement.id)
        .order_by(IncomeStatementLineItem.line_order)
        .all()
    )

    if not line_items:
        print(f"No line items found for {company_ticker} {time_period} income statement")
        return

    # Create output file
    period_clean = time_period.replace(" ", "")
    output_file = output_dir / f"{company_ticker}_IS_{period_clean}.csv"

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["row_name", "section", "is_calculated", "standardized_name", "company"])

        for item in line_items:
            writer.writerow(
                [
                    item.line_name,
                    item.line_category or "",
                    item.is_calculated if item.is_calculated is not None else "",
                    item.standardized_name or "",
                    company.name,
                ]
            )

    print(f"✓ Exported income statement to {output_file}")
    print(f"  {len(line_items)} line items")


def main():
    parser = argparse.ArgumentParser(
        description="Export financial statement data for tiger-transformer retraining"
    )
    parser.add_argument("ticker", help="Company ticker symbol (e.g., ADBE)")
    parser.add_argument("period", help="Time period (e.g., 'Q4 2025')")
    parser.add_argument(
        "--statement",
        choices=["bs", "is", "both"],
        default="both",
        help="Statement type to export (default: both)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/tiger-transformer_add_data",
        help="Output directory (default: data/tiger-transformer_add_data)",
    )

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create database session
    db = SessionLocal()

    try:
        if args.statement in ["bs", "both"]:
            export_balance_sheet(db, args.ticker.upper(), args.period, output_dir)

        if args.statement in ["is", "both"]:
            export_income_statement(db, args.ticker.upper(), args.period, output_dir)

    finally:
        db.close()


if __name__ == "__main__":
    main()
