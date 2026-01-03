"""
Historical calculations routes
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.balance_sheet import BalanceSheet
from app.models.document import Document
from app.models.historical_calculation import HistoricalCalculation
from app.models.income_statement import IncomeStatement
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.historical_calculation import HistoricalCalculation as HistoricalCalculationSchema
from app.utils.historical_calculations import calculate_all_historical_metrics

router = APIRouter()


def calculate_and_save_historical_calculations(
    document_id: str, db: Session
) -> HistoricalCalculation:
    """
    Calculate historical financial metrics and save to database.
    """
    # Get document
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get balance sheet and income statement
    balance_sheet = db.query(BalanceSheet).filter(BalanceSheet.document_id == document_id).first()
    income_statement = (
        db.query(IncomeStatement).filter(IncomeStatement.document_id == document_id).first()
    )

    if not balance_sheet:
        raise HTTPException(status_code=404, detail="Balance sheet not found for this document")

    if not income_statement:
        raise HTTPException(status_code=404, detail="Income statement not found for this document")

    # Calculate all metrics
    results = calculate_all_historical_metrics(balance_sheet, income_statement)

    # Convert calculation notes list to JSON string
    import json

    calculation_notes_json = (
        json.dumps(results["calculation_notes"]) if results["calculation_notes"] else None
    )

    # Check if historical calculation already exists
    existing_calc = (
        db.query(HistoricalCalculation)
        .filter(HistoricalCalculation.document_id == document_id)
        .first()
    )

    if existing_calc:
        # Update existing
        existing_calc.net_working_capital = results["net_working_capital"]
        existing_calc.net_long_term_operating_assets = results["net_long_term_operating_assets"]
        existing_calc.invested_capital = results["invested_capital"]
        existing_calc.capital_turnover = results["capital_turnover"]
        existing_calc.ebita = results["ebita"]
        existing_calc.ebita_margin = results["ebita_margin"]
        existing_calc.effective_tax_rate = results["effective_tax_rate"]
        existing_calc.calculation_notes = calculation_notes_json
        existing_calc.time_period = document.time_period
        existing_calc.currency = balance_sheet.currency or income_statement.currency
        existing_calc.unit = balance_sheet.unit or income_statement.unit
        db.commit()
        db.refresh(existing_calc)
        return existing_calc
    else:
        # Create new
        new_calc = HistoricalCalculation(
            id=str(uuid.uuid4()),
            document_id=document_id,
            net_working_capital=results["net_working_capital"],
            net_long_term_operating_assets=results["net_long_term_operating_assets"],
            invested_capital=results["invested_capital"],
            capital_turnover=results["capital_turnover"],
            ebita=results["ebita"],
            ebita_margin=results["ebita_margin"],
            effective_tax_rate=results["effective_tax_rate"],
            calculation_notes=calculation_notes_json,
            time_period=document.time_period,
            currency=balance_sheet.currency or income_statement.currency,
            unit=balance_sheet.unit or income_statement.unit,
        )
        db.add(new_calc)
        db.commit()
        db.refresh(new_calc)
        return new_calc


@router.get("/{document_id}/historical-calculations", response_model=HistoricalCalculationSchema)
def get_historical_calculations(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get historical calculations for a document.
    """
    # Check if document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get historical calculation
    calc = (
        db.query(HistoricalCalculation)
        .filter(HistoricalCalculation.document_id == document_id)
        .first()
    )

    if not calc:
        raise HTTPException(
            status_code=404, detail="Historical calculations not found for this document"
        )

    return calc


@router.post(
    "/{document_id}/historical-calculations/recalculate", response_model=HistoricalCalculationSchema
)
def recalculate_historical_calculations(
    document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Recalculate historical calculations for a document.
    """
    try:
        calc = calculate_and_save_historical_calculations(document_id, db)
        return calc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating historical metrics: {str(e)}"
        )


# Test endpoints (for development)
@router.get(
    "/{document_id}/historical-calculations/test", response_model=HistoricalCalculationSchema
)
def get_historical_calculations_test(document_id: str, db: Session = Depends(get_db)):
    """
    Test endpoint: Get historical calculations for a document (no auth required).
    """
    # Check if document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get historical calculation
    calc = (
        db.query(HistoricalCalculation)
        .filter(HistoricalCalculation.document_id == document_id)
        .first()
    )

    if not calc:
        raise HTTPException(
            status_code=404, detail="Historical calculations not found for this document"
        )

    return calc


@router.post(
    "/{document_id}/historical-calculations/recalculate/test",
    response_model=HistoricalCalculationSchema,
)
def recalculate_historical_calculations_test(document_id: str, db: Session = Depends(get_db)):
    """
    Test endpoint: Recalculate historical calculations (no auth required).
    """
    try:
        calc = calculate_and_save_historical_calculations(document_id, db)
        return calc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating historical metrics: {str(e)}"
        )
