"""
Timeline service for cross-document date validation and healing.

This service implements Stage 2 of the date refactor plan:
- Fetches all processed documents for a company
- Sorts them by period_end_date to create a timeline
- Learns the fiscal year pattern from Q4/FY anchors
- Fills in missing dates using the learned 3-month pattern
- Validates consistency across the timeline
"""

from datetime import datetime, timedelta
from typing import Any

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.models.document import Document, ProcessingStatus


def _parse_time_period(time_period: str | None) -> tuple[int, int] | None:
    """
    Parse time_period string into (year, quarter) tuple.

    Args:
        time_period: String like "Q3 2024" or "FY 2024"

    Returns:
        Tuple of (year, quarter) where quarter is 1-4, or None if invalid
    """
    if not time_period:
        return None

    parts = time_period.strip().split()
    if len(parts) != 2:
        return None

    period, year_str = parts
    try:
        year = int(year_str)
    except ValueError:
        return None

    if period == "FY" or period == "Q4":
        return (year, 4)
    elif period == "Q3":
        return (year, 3)
    elif period == "Q2":
        return (year, 2)
    elif period == "Q1":
        return (year, 1)

    return None


def _get_sort_key(doc: Document) -> datetime:
    """
    Generate a synthetic sort key for timeline ordering.

    Priority:
    1. period_end_date (if available)
    2. document_date minus 45 days (proxy for period end)
    3. Fallback to very old date

    Args:
        doc: Document object

    Returns:
        datetime object for sorting
    """
    # Priority 1: period_end_date
    if doc.period_end_date:
        try:
            return datetime.strptime(doc.period_end_date, "%Y-%m-%d")
        except ValueError:
            pass

    # Priority 2: document_date minus 45 days
    if doc.document_date:
        try:
            doc_date = datetime.strptime(doc.document_date, "%Y-%m-%d")
            return doc_date - timedelta(days=45)
        except ValueError:
            pass

    # Fallback: very old date
    return datetime(1900, 1, 1)


def _find_q4_anchors(sorted_docs: list[Document]) -> list[tuple[Document, datetime]]:
    """
    Find Q4/FY documents with valid period_end_date to use as anchors.

    Args:
        sorted_docs: Documents sorted by timeline

    Returns:
        List of (document, period_end_date) tuples for Q4/FY anchors
    """
    anchors = []
    for doc in sorted_docs:
        if doc.time_period and doc.period_end_date:
            parsed = _parse_time_period(doc.time_period)
            if parsed and parsed[1] == 4:  # Q4 or FY
                try:
                    date_obj = datetime.strptime(doc.period_end_date, "%Y-%m-%d")
                    anchors.append((doc, date_obj))
                except ValueError:
                    pass
    return anchors


def _infer_period_end_date_from_pattern(
    time_period: str, q4_anchors: list[tuple[Document, datetime]]
) -> str | None:
    """
    Infer period_end_date from time_period using learned pattern from Q4 anchors.

    Args:
        time_period: Time period like "Q2 2024"
        q4_anchors: List of Q4/FY anchor documents with dates

    Returns:
        Inferred period_end_date or None
    """
    parsed = _parse_time_period(time_period)
    if not parsed:
        return None

    year, quarter = parsed

    # Find the closest Q4 anchor by year proximity
    # We want Q4 from the same year or the closest year
    closest_anchor = None
    min_year_diff = None

    for anchor_doc, anchor_date in q4_anchors:
        anchor_parsed = _parse_time_period(anchor_doc.time_period)
        if anchor_parsed:
            anchor_year, _ = anchor_parsed
            year_diff = abs(anchor_year - year)

            # Prefer Q4 from same year, then previous/next year
            if min_year_diff is None or year_diff < min_year_diff:
                min_year_diff = year_diff
                closest_anchor = (anchor_year, anchor_date)

    if not closest_anchor:
        return None

    anchor_year, anchor_date = closest_anchor

    # Calculate offset from Q4
    quarters_back = 4 - quarter

    # Go back N quarters (3 months each)
    inferred_date = anchor_date - relativedelta(months=3 * quarters_back)

    # Adjust year if needed
    if anchor_year > year:
        inferred_date = inferred_date - relativedelta(years=1)
    elif anchor_year < year:
        inferred_date = inferred_date + relativedelta(years=(year - anchor_year))

    return inferred_date.strftime("%Y-%m-%d")


def _infer_time_period_from_pattern(
    period_end_date: str, q4_anchors: list[tuple[Document, datetime]]
) -> str | None:
    """
    Infer time_period from period_end_date using learned pattern from Q4 anchors.

    Args:
        period_end_date: Date string in YYYY-MM-DD format
        q4_anchors: List of Q4/FY anchor documents with dates

    Returns:
        Inferred time_period like "Q2 2024" or None
    """
    try:
        target_date = datetime.strptime(period_end_date, "%Y-%m-%d")
    except ValueError:
        return None

    # Find the closest Q4 anchor (using months for consistency with validation)
    closest_anchor = None
    min_diff = None

    for anchor_doc, anchor_date in q4_anchors:
        diff = abs(
            (target_date.year - anchor_date.year) * 12 + (target_date.month - anchor_date.month)
        )
        if min_diff is None or diff < min_diff:
            min_diff = diff
            closest_anchor = (anchor_doc, anchor_date)

    if not closest_anchor:
        return None

    anchor_doc, anchor_date = closest_anchor
    anchor_parsed = _parse_time_period(anchor_doc.time_period)
    if not anchor_parsed:
        return None

    anchor_year, _ = anchor_parsed

    # Calculate months difference
    months_diff = (target_date.year - anchor_date.year) * 12 + (
        target_date.month - anchor_date.month
    )

    # Convert to quarters (round to nearest quarter)
    quarters_diff = round(months_diff / 3)

    # Calculate target quarter
    target_quarter = 4 + quarters_diff
    target_year = anchor_year

    # Normalize quarter and year
    while target_quarter > 4:
        target_quarter -= 4
        target_year += 1
    while target_quarter < 1:
        target_quarter += 4
        target_year -= 1

    return f"Q{target_quarter} {target_year}"


def heal_company_timelines(
    company_id: str, db: Session, current_document_id: str | None = None
) -> dict[str, Any]:
    """
    Heal missing or inconsistent dates across all documents for a company.

    This implements Stage 2 of the date refactor plan:
    - Fetches all processed documents
    - Sorts by timeline
    - Uses Q4/FY as anchors to learn the fiscal year pattern
    - Fills gaps using the learned 3-month pattern
    - Validates the CURRENT document only (if provided)

    Args:
        company_id: Company ID
        db: Database session
        current_document_id: ID of the document currently being processed (optional)

    Returns:
        Dictionary with healing statistics
    """
    # Fetch all processed documents for this company
    # CRITICAL: We must include the current document even if it's not yet INDEXED
    # It might be in CLASSIFYING, PENDING, or other states
    query = db.query(Document).filter(Document.company_id == company_id)

    if current_document_id:
        # If processing a specific doc, fetch INDEXED + that specific doc
        from sqlalchemy import or_

        query = query.filter(
            or_(
                Document.indexing_status == ProcessingStatus.INDEXED,
                Document.id == current_document_id,
            )
        )
    else:
        # Otherwise just fetch INDEXED documents
        query = query.filter(Document.indexing_status == ProcessingStatus.INDEXED)

    documents = query.all()

    # Exclude triple-null documents
    valid_docs = [
        doc for doc in documents if doc.time_period or doc.period_end_date or doc.document_date
    ]

    # Pre-condition: Need at least 4 documents
    if len(valid_docs) < 4:
        print(f"[Timeline Healing] Skipping: Only {len(valid_docs)} documents (need 4+)")
        return {
            "healed": False,
            "reason": f"Insufficient documents ({len(valid_docs)} < 4)",
            "documents_processed": 0,
        }

    # Sort by synthetic timeline key
    sorted_docs = sorted(valid_docs, key=_get_sort_key)

    # Find Q4/FY anchors (source of truth for fiscal year pattern)
    q4_anchors = _find_q4_anchors(sorted_docs)

    if not q4_anchors:
        print(
            f"[Timeline Healing] Skipping: No Q4/FY anchors found among {len(valid_docs)} documents"
        )
        return {
            "healed": False,
            "reason": "No Q4/FY anchors found to learn fiscal year pattern",
            "documents_processed": len(valid_docs),
        }

    print(
        f"[Timeline Healing] Starting for company {company_id}: {len(valid_docs)} docs, {len(q4_anchors)} Q4 anchors"
    )
    if current_document_id:
        print(f"[Timeline Healing] Current document: {current_document_id}")

    healed_count = 0

    # Fill missing period_end_date based on time_period using learned pattern
    # This applies to ALL documents
    for doc in sorted_docs:
        if not doc.period_end_date and doc.time_period:
            inferred = _infer_period_end_date_from_pattern(doc.time_period, q4_anchors)
            if inferred:
                doc.period_end_date = inferred
                healed_count += 1

    # Fill missing time_period based on period_end_date using learned pattern
    # This applies to ALL documents
    for doc in sorted_docs:
        if not doc.time_period and doc.period_end_date:
            inferred = _infer_time_period_from_pattern(doc.period_end_date, q4_anchors)
            if inferred:
                doc.time_period = inferred
                healed_count += 1

    # Context-aware validation for CURRENT document only
    if current_document_id:
        current_doc = next((d for d in sorted_docs if d.id == current_document_id), None)

        if not current_doc:
            print(
                f"[Timeline Healing] WARNING: Current document {current_document_id} not found in sorted_docs!"
            )
            print(f"[Timeline Healing] Available docs: {[d.id for d in sorted_docs]}")
            # Check if it was filtered out due to status?
            raw_doc = db.query(Document).filter(Document.id == current_document_id).first()
            if raw_doc:
                print(
                    f"[Timeline Healing] Raw doc status: {raw_doc.indexing_status}, TP: {raw_doc.time_period}, PED: {raw_doc.period_end_date}"
                )
        elif not current_doc.time_period or not current_doc.period_end_date:
            print("[Timeline Healing] WARNING: Current doc missing required fields for validation.")
            print(
                f"[Timeline Healing] TP: {current_doc.time_period}, PED: {current_doc.period_end_date}"
            )

        if current_doc and current_doc.time_period and current_doc.period_end_date:
            print(
                f"[Timeline Healing] Validating current doc: time_period={current_doc.time_period}, period_end_date={current_doc.period_end_date}"
            )

            # Filter anchors to exclude the current document itself
            # This prevents "self-validation" where a wrongly labeled Q4 validates itself
            validation_anchors = [(d, dt) for (d, dt) in q4_anchors if d.id != current_doc.id]

            if not validation_anchors:
                print(
                    "[Timeline Healing] No other Q4 anchors found to validate against. Accepting current values."
                )
                expected_time_period = current_doc.time_period
            else:
                # Use the inference function to determine what the pattern thinks the Time Period should be
                # This handles all the complex date math (Q4 matching, modulo 12, etc.) correctly
                expected_time_period = _infer_time_period_from_pattern(
                    current_doc.period_end_date, validation_anchors
                )

            if expected_time_period:
                print(f"[Timeline Healing] Pattern expects: {expected_time_period}")

                # Compare expected (inferred) with actual
                if expected_time_period != current_doc.time_period:
                    print(
                        f"[Timeline Healing] MISMATCH DETECTED: {current_doc.time_period} vs {expected_time_period}"
                    )

                    # Double check they aren't equivalent (e.g. FY 2024 vs Q4 2024)
                    # Although for consistency we might strictly prefer one
                    current_parsed = _parse_time_period(current_doc.time_period)
                    expected_parsed = _parse_time_period(expected_time_period)

                    if current_parsed and expected_parsed:
                        curr_year, curr_q = current_parsed
                        exp_year, exp_q = expected_parsed

                        if curr_year != exp_year or curr_q != exp_q:
                            print(
                                f"[Timeline Healing] FIXING: {current_doc.time_period} → {expected_time_period}"
                            )
                            current_doc.time_period = expected_time_period
                            healed_count += 1
                        else:
                            print(
                                "[Timeline Healing] Semantically equivalent (e.g. Q4 vs FY), no change"
                            )
                else:
                    print("[Timeline Healing] Validation passed: matches pattern")
            else:
                print("[Timeline Healing] Could not infer expected time period from pattern")

    # Commit changes
    if healed_count > 0:
        db.commit()
        print(f"[Timeline Healing] Completed: Healed {healed_count} field(s)")
    else:
        print("[Timeline Healing] Completed: No changes needed")

    return {
        "healed": True,
        "documents_processed": len(valid_docs),
        "fields_healed": healed_count,
        "q4_anchors_found": len(q4_anchors),
    }
