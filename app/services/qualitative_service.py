"""
Service for managing qualitative company assessments.
"""

from sqlalchemy.orm import Session

from app.app_agents.qualitative_extractor import extract_qualitative_assessment
from app.models.company import Company
from app.models.qualitative_assessment import QualitativeAssessment


def run_qualitative_assessment(db: Session, company_id: str) -> QualitativeAssessment:
    """
    Runs the qualitative assessment agent for a company and persists the results.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise ValueError(f"Company with ID {company_id} not found")

    # Call agent
    scan_name = company.name if company.name and company.name != "Unknown" else company.ticker
    scan_ticker = company.ticker or ""

    result_json = extract_qualitative_assessment(scan_ticker, scan_name)

    # Upsert logic
    # Check if assessment exists
    assessment = (
        db.query(QualitativeAssessment)
        .filter(QualitativeAssessment.company_id == company_id)
        .first()
    )

    if not assessment:
        assessment = QualitativeAssessment(company_id=company_id)
        db.add(assessment)

    # Update fields
    assessment.economic_moat_label = result_json.get("economic_moat_label")
    assessment.economic_moat_rationale = result_json.get("economic_moat_rationale")
    assessment.near_term_growth_label = result_json.get("near_term_growth_label")
    assessment.near_term_growth_rationale = result_json.get("near_term_growth_rationale")
    assessment.revenue_predictability_label = result_json.get("revenue_predictability_label")
    assessment.revenue_predictability_rationale = result_json.get(
        "revenue_predictability_rationale"
    )

    db.commit()
    db.refresh(assessment)
    return assessment


def get_qualitative_assessment(db: Session, company_id: str) -> QualitativeAssessment | None:
    """
    Retrieve existing assessment.
    """
    return (
        db.query(QualitativeAssessment)
        .filter(QualitativeAssessment.company_id == company_id)
        .first()
    )
