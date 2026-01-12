import logging
import os
import uuid
from datetime import datetime

from sqlalchemy.orm import Session, configure_mappers

from app.core.security import get_password_hash
from app.models.balance_sheet import BalanceSheet, BalanceSheetLineItem

# Ensure all models are imported so relationships are registered
# This prevents Mapper errors when creating instances
from app.models.company import Company
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.document_status import DocumentStatus
from app.models.financial_assumption import FinancialAssumption
from app.models.historical_calculation import HistoricalCalculation
from app.models.income_statement import IncomeStatement, IncomeStatementLineItem
from app.models.non_operating_classification import (
    NonOperatingClassification,
    NonOperatingClassificationItem,
)
from app.models.organic_growth import OrganicGrowth
from app.models.user import User

logger = logging.getLogger(__name__)


def init_db(db: Session):
    """
    Seed the database with development data if in development environment.
    Creates:
    - Dev user (dev@example.com)
    - Fake Railroad Company with full financial historical data
    """
    if os.getenv("ENVIRONMENT", "development") != "development":
        return

    logger.info("Initializing database seeding...")

    # Ensure mappers are configured to avoid SQLAlchemy warnings/errors
    configure_mappers()

    # 1. Seed Dev User
    email = "dev@example.com"
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            id=email,
            email=email,
            first_name="Dev",
            last_name="User",
            hashed_password=get_password_hash("devpassword"),
            auth_provider="local",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created dev user: {email}")
    else:
        logger.info(f"Dev user already exists: {email}")

    # 2. Seed Fake Railroad Company (If it doesn't exist)
    company_id = "test-company-railroad"
    company = db.query(Company).filter(Company.id == company_id).first()

    if not company:
        logger.info("Seeding Fake Railroad Company data...")
        try:
            # 2.1 Create Company
            company = Company(
                id=company_id, name="Fake Railroad Company for Testing, Inc.", ticker="TESTING"
            )
            db.add(company)

            # 2.2 Setup Document
            doc_id = "test-document-railroad-q4"
            doc_filename = "test_railroad_report.pdf"
            doc_path = os.path.join("data", "uploads", f"{doc_id}.pdf")

            document = Document(
                id=doc_id,
                user_id=user.id,
                company_id=company_id,
                filename=doc_filename,
                file_path=doc_path,
                document_type=DocumentType.EARNINGS_ANNOUNCEMENT,
                time_period="Q4 2024",
                period_end_date="2024-12-31",
                status=DocumentStatus.PROCESSING_COMPLETE,
                current_step="7/7: Processing Complete",
                indexing_status=ProcessingStatus.INDEXED,
                analysis_status=ProcessingStatus.PROCESSED,
                summary="This is a fake summary for a fake railroad company used for testing and demonstration.",
                page_count=13,
                character_count=25000,
                uploaded_at=datetime.utcnow(),
                indexed_at=datetime.utcnow(),
                processed_at=datetime.utcnow(),
            )
            db.add(document)

            # 2.3 Balance Sheet
            bs_id = str(uuid.uuid4())
            balance_sheet = BalanceSheet(
                id=bs_id,
                document_id=doc_id,
                time_period="Q4 2024",
                currency="USD",
                unit="millions",
                is_valid=True,
                chunk_index=3,
            )
            db.add(balance_sheet)

            bs_items_data = [
                (
                    "Cash & Equivalents (Cash and cash equivalents)",
                    1016.0,
                    "Current Assets",
                    False,
                    0,
                ),
                ("Short-term investments", 20.0, "Current Assets", False, 1),
                ("Other Current Assets (Other current assets)", 2985.0, "Current Assets", True, 2),
                ("Investments", 2664.0, "Non-Current Assets", False, 3),
                (
                    "Property, Plant & Equipment (Properties, net)",
                    58343.0,
                    "Non-Current Assets",
                    True,
                    4,
                ),
                ("Operating lease assets", 1297.0, "Non-Current Assets", False, 5),
                ("Other Non-Current Assets (Other assets)", 1390.0, "Non-Current Assets", True, 6),
                ("Total Assets (Total assets)", 67715.0, "Total Assets", None, 7),
                (
                    "Short-Term Debt (Debt due within one year)",
                    1425.0,
                    "Current Liabilities",
                    False,
                    8,
                ),
                (
                    "Other Current Liabilities (Other current liabilities)",
                    3829.0,
                    "Current Liabilities",
                    False,
                    9,
                ),
                (
                    "Long-Term Debt (Debt due after one year)",
                    29767.0,
                    "Non-Current Liabilities",
                    False,
                    10,
                ),
                ("Operating lease liabilities", 925.0, "Non-Current Liabilities", False, 11),
                ("Deferred income taxes", 13151.0, "Non-Current Liabilities", True, 12),
                (
                    "Other Non-Current Liabilities (Other long-term liabilities)",
                    1728.0,
                    "Non-Current Liabilities",
                    False,
                    13,
                ),
                ("Total Liabilities (Total liabilities)", 50825.0, "Total Liabilities", None, 14),
                ("Common Equity (Total common shareholders' equity)", 16890.0, "Equity", False, 15),
                (
                    "Total Liabilities & Equity (Total liabilities and common shareholders' equity)",
                    67715.0,
                    "Total Liabilities and Equity",
                    None,
                    16,
                ),
            ]

            for line_name, value, cat, is_op, order in bs_items_data:
                item = BalanceSheetLineItem(
                    id=str(uuid.uuid4()),
                    balance_sheet_id=bs_id,
                    line_name=line_name,
                    line_value=value,
                    line_category=cat,
                    is_operating=is_op,
                    line_order=order,
                )
                db.add(item)

            # 2.4 Income Statement
            is_id = str(uuid.uuid4())
            income_statement = IncomeStatement(
                id=is_id,
                document_id=doc_id,
                time_period="Q4 2024",
                currency="$",
                unit="millions",
                revenue_prior_year=5801.0,
                revenue_prior_year_unit="millions",
                revenue_growth_yoy=5.5163,
                basic_shares_outstanding=604.2,
                basic_shares_outstanding_unit="millions",
                diluted_shares_outstanding=605.2,
                diluted_shares_outstanding_unit="millions",
                is_valid=True,
                chunk_index=2,
            )
            db.add(income_statement)

            is_items_data = [
                ("Freight revenues", 5789.0, "Recurring", True, 0),
                ("Other revenues", 332.0, "Recurring", True, 1),
                ("Total Net Revenue (Total operating revenues)", 6121.0, "Total", None, 2),
                ("Compensation and benefits", 1261.0, "Recurring", True, 3),
                ("Purchased services and materials", -619.0, "Recurring", True, 4),
                ("Fuel", -581.0, "Recurring", True, 5),
                ("Depreciation", -606.0, "Recurring", True, 6),
                ("Equipment and other rents", -248.0, "Recurring", True, 7),
                ("Other", -281.0, "Recurring", True, 8),
                ("Total Net Revenue (Total operating expenses)", 3596.0, "Total", None, 9),
                ("Operating Income (Operating Income)", 2525.0, "Recurring", True, 10),
                ("Other income, net", 68.0, "Recurring", False, 11),
                ("Interest expense", -312.0, "Recurring", False, 12),
                ("Pretax Income (Income before income taxes)", 2281.0, "Total", None, 13),
                ("Tax Expense (Income tax expense)", -519.0, "Recurring", True, 14),
                ("Net Income (Net Income)", 1762.0, "Total", None, 15),
            ]

            for line_name, value, cat, is_op, order in is_items_data:
                item = IncomeStatementLineItem(
                    id=str(uuid.uuid4()),
                    income_statement_id=is_id,
                    line_name=line_name,
                    line_value=value,
                    line_category=cat,
                    is_operating=is_op,
                    line_order=order,
                )
                db.add(item)

            # 2.5 Financial Assumptions
            assumption = FinancialAssumption(
                id=str(uuid.uuid4()),
                company_id=company_id,
                revenue_growth_stage1=0.0552,
                revenue_growth_stage2=0.0426,
                revenue_growth_terminal=0.03,
                ebita_margin_stage1=0.4125,
                ebita_margin_stage2=0.4125,
                ebita_margin_terminal=0.4125,
                marginal_capital_turnover_stage1=0.494,
                marginal_capital_turnover_stage2=0.494,
                marginal_capital_turnover_terminal=0.494,
                adjusted_tax_rate=0.2297,
                wacc=0.08,
            )
            db.add(assumption)

            # 2.6 Historical Calculations
            calc = HistoricalCalculation(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                time_period="Q4 2024",
                currency="USD",
                unit="millions",
                calculated_at=datetime.utcnow(),
                net_working_capital=2985.0,
                net_long_term_operating_assets=46582.0,
                invested_capital=49567.0,
                capital_turnover=0.494,
                ebita=2525.0,
                ebita_margin=0.4125,
                effective_tax_rate=0.2275,
                adjusted_tax_rate=0.2297,
                nopat=1945.01,
                roic=0.157,
                net_working_capital_breakdown='{"total": 2985.0, "current_assets": [{"line_name": "Other Current Assets (Other current assets)", "line_value": 2985.0, "line_category": "Current Assets", "is_operating": true}], "current_liabilities": [], "current_assets_total": 2985.0, "current_liabilities_total": 0.0}',
                net_long_term_operating_assets_breakdown='{"total": 46582.0, "non_current_assets": [{"line_name": "Property, Plant & Equipment (Properties, net)", "line_value": 58343.0, "line_category": "Non-Current Assets", "is_operating": true}, {"line_name": "Other Non-Current Assets (Other assets)", "line_value": 1390.0, "line_category": "Non-Current Assets", "is_operating": true}], "non_current_liabilities": [{"line_name": "Deferred income taxes", "line_value": 13151.0, "line_category": "Non-Current Liabilities", "is_operating": true}], "non_current_assets_total": 59733.0, "non_current_liabilities_total": 13151.0}',
                ebita_breakdown='{"total": 2525.0, "operating_income": 2525.0, "adjustments": []}',
                adjusted_tax_rate_breakdown='{"adjusted_tax_rate": 0.2297, "reported_tax_expense": 519.0, "adjusted_tax_expense": 580.0, "adjustments": [{"line_name": "Other income, net", "line_value": 68.0, "tax_effect": -17.0, "source": "Intermediate"}, {"line_name": "Interest expense", "line_value": -312.0, "tax_effect": 78.0, "source": "Intermediate"}], "marginal_rate": 0.25, "ebita": 2525.0}',
            )
            db.add(calc)

            # 2.7 Organic Growth
            og = OrganicGrowth(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                time_period="Q4 2024",
                currency="$",
                prior_period_revenue=5801.0,
                prior_period_revenue_unit="millions",
                current_period_revenue=6121.0,
                current_period_revenue_unit="millions",
                simple_revenue_growth=5.5163,
                acquisition_revenue_impact=0.0,
                current_period_adjusted_revenue=6121.0,
                current_period_adjusted_revenue_unit="millions",
                organic_revenue_growth=5.5163,
                chunk_index=5,
                is_valid=True,
                extraction_date=datetime.utcnow(),
            )
            db.add(og)

            # 2.8 Non-Operating Classification
            noc_id = str(uuid.uuid4())
            noc = NonOperatingClassification(
                id=noc_id,
                document_id=doc_id,
                time_period="Q4 2024",
                extraction_date=datetime.utcnow(),
            )
            db.add(noc)

            noc_items_data = [
                (
                    "Cash & Equivalents (Cash and cash equivalents)",
                    1016.0,
                    "millions",
                    "cash",
                    "balance_sheet",
                    0,
                ),
                (
                    "Short-term investments",
                    20.0,
                    "millions",
                    "short_term_investments",
                    "balance_sheet",
                    1,
                ),
                (
                    "Investments",
                    2664.0,
                    "millions",
                    "other_financial_physical_assets",
                    "balance_sheet",
                    2,
                ),
                (
                    "Operating lease assets",
                    1297.0,
                    "millions",
                    "operating_lease_related",
                    "balance_sheet",
                    3,
                ),
                (
                    "Short-Term Debt (Debt due within one year)",
                    1425.0,
                    "millions",
                    "debt",
                    "balance_sheet",
                    4,
                ),
                (
                    "Other Current Liabilities (Other current liabilities)",
                    3829.0,
                    "millions",
                    "other_financial_liabilities",
                    "balance_sheet",
                    5,
                ),
                (
                    "Long-Term Debt (Debt due after one year)",
                    29767.0,
                    "millions",
                    "debt",
                    "balance_sheet",
                    6,
                ),
                (
                    "Operating lease liabilities",
                    925.0,
                    "millions",
                    "operating_lease_related",
                    "balance_sheet",
                    7,
                ),
                (
                    "Other Non-Current Liabilities (Other long-term liabilities)",
                    1728.0,
                    "millions",
                    "other_financial_liabilities",
                    "balance_sheet",
                    8,
                ),
                (
                    "Common Equity (Total common shareholders' equity)",
                    16890.0,
                    "millions",
                    "common_equity",
                    "balance_sheet",
                    9,
                ),
            ]

            for name, val, unit, cat, src, order in noc_items_data:
                noc_item = NonOperatingClassificationItem(
                    id=str(uuid.uuid4()),
                    classification_id=noc_id,
                    line_name=name,
                    line_value=val,
                    unit=unit,
                    category=cat,
                    source=src,
                    line_order=order,
                )
                db.add(noc_item)

            db.commit()
            logger.info(f"Successfully seeded Fake Railroad Company data for: {company.name}")

            # 2.9 Create Fake PDF file on disk
            os.makedirs(os.path.dirname(doc_path), exist_ok=True)
            if not os.path.exists(doc_path):
                with open(doc_path, "wb") as f:
                    f.write(
                        b"%PDF-1.4\n1 0 obj\n<< /Title (Fake Report) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
                    )
                logger.info(f"Created fake PDF at: {doc_path}")

        except Exception as e:
            db.rollback()
            logger.error(f"Error seeding Fake Railroad Company data: {e}")
            # We don't raise here to allow the app to still start even if seeding fails
    else:
        logger.info(f"Fake Railroad Company already exists (ID: {company_id})")
