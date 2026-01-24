"""
Document processing service for classification, duplication checks, summaries, and indexing.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from agents.document_classifier import classify_document
from agents.document_summarizer import generate_document_summary
from app.models.company import Company
from app.models.document import Document, DocumentType, ProcessingStatus
from app.utils.document_hash import generate_document_hash
from app.utils.document_indexer import index_document_chunks
from app.utils.duplicate_detector import check_duplicate_document
from app.utils.financial_statement_progress import (
    FinancialStatementMilestone,
    MilestoneStatus,
    add_log,
    update_milestone,
)
from app.utils.pdf_extractor import extract_text_from_pdf


class DocumentProcessingMode(Enum):
    PREVIEW = "preview"
    FULL = "full"
    INDEX_ONLY = "index_only"


@dataclass
class DocumentProcessingResult:
    classification_data: dict
    duplicate_check: dict | None
    summary: str | None
    extracted_text_preview: str
    document_hash: str
    total_pages: int
    character_count: int
    company: Company


def process_document(
    *,
    db_session,
    mode: DocumentProcessingMode,
    file_path: str | None = None,
    filename: str | None = None,
    document_id: str | None = None,
    document: Document | None = None,
    chunk_size: int = 5000,
) -> DocumentProcessingResult | None:
    """
    Process a document according to the requested mode.

    PREVIEW: classify, detect duplicates, generate summary; no status updates.
    FULL: classify, detect duplicates, generate summary, index chunks, update status.
    INDEX_ONLY: index chunks and update status for an already classified document.
    """
    if document is None and document_id:
        document = db_session.query(Document).filter(Document.id == document_id).first()

    if mode != DocumentProcessingMode.PREVIEW and document is None:
        raise ValueError("Document record is required for non-preview processing.")

    resolved_file_path = file_path or (document.file_path if document else None)
    resolved_filename = filename or (document.filename if document else None)

    if not resolved_file_path or not resolved_filename:
        raise ValueError("File path and filename are required for document processing.")

    if mode == DocumentProcessingMode.INDEX_ONLY:
        if not os.path.exists(resolved_file_path):
            document.indexing_status = ProcessingStatus.ERROR
            db_session.commit()
            return None

        if document.indexing_status != ProcessingStatus.INDEXING:
            document.indexing_status = ProcessingStatus.INDEXING
            db_session.commit()

        index_document_chunks(resolved_file_path, document.id, chunk_size=chunk_size)

        _, total_pages, character_count = extract_text_from_pdf(resolved_file_path, max_pages=None)
        document.indexing_status = ProcessingStatus.INDEXED
        document.indexed_at = datetime.utcnow()
        document.page_count = total_pages
        document.character_count = character_count
        db_session.commit()
        return None

    if mode == DocumentProcessingMode.FULL:
        document.indexing_status = ProcessingStatus.CLASSIFYING
        db_session.commit()

    if not os.path.exists(resolved_file_path):
        if document:
            document.indexing_status = ProcessingStatus.ERROR
            db_session.commit()
        raise ValueError(f"File not found for document processing: {resolved_file_path}")

    # Shadowing status: Start Classification (only if document exists)
    if document:
        update_milestone(
            document.id,
            FinancialStatementMilestone.CLASSIFICATION,
            MilestoneStatus.IN_PROGRESS,
            message="I'm identifying the document type and company...",
        )

    extracted_text, total_pages, character_count = extract_text_from_pdf(
        resolved_file_path, max_pages=5
    )
    extracted_text_preview = extracted_text[:500]
    if document:
        add_log(
            document.id,
            FinancialStatementMilestone.CLASSIFICATION,
            f"I've read the first few pages ({min(total_pages, 5)}) to get a sense of the document.",
        )

    hash_text = extracted_text[:5000] if len(extracted_text) > 5000 else extracted_text
    document_hash = generate_document_hash(hash_text)

    if document:
        add_log(
            document.id,
            FinancialStatementMilestone.CLASSIFICATION,
            "I'm asking Gemini to identify the company name, ticker, and document type from the extracted text.",
        )

    classification_data = classify_document(extracted_text)

    if document:
        add_log(
            document.id,
            FinancialStatementMilestone.CLASSIFICATION,
            f"Gemini has identified this as a {classification_data.get('document_type')} for {classification_data.get('company_name')} ({classification_data.get('ticker')}).",
        )

    ticker = (
        classification_data.get("ticker").strip().upper()
        if classification_data.get("ticker")
        else None
    )
    company_name = (
        classification_data.get("company_name").strip()
        if classification_data.get("company_name")
        else None
    )

    if not ticker and not company_name:
        if document:
            document.indexing_status = ProcessingStatus.ERROR
            db_session.commit()
            update_milestone(
                document.id,
                FinancialStatementMilestone.CLASSIFICATION,
                MilestoneStatus.ERROR,
                message="Could not identify company (no ticker or name)",
            )
        raise ValueError("Could not identify company (no ticker or name) from document.")

    # Shadowing status: Classification Success (only if document exists)
    if document:
        update_milestone(
            document.id,
            FinancialStatementMilestone.CLASSIFICATION,
            MilestoneStatus.COMPLETED,
            message=f"I've identified this as a {classification_data.get('document_type')} for {company_name or ticker}.",
        )

    # 1. Try to find by ticker (the primary unique identifier)
    company = None
    if ticker:
        company = db_session.query(Company).filter(Company.ticker == ticker).first()

    # 2. Fallback to name if not found by ticker
    if not company and company_name:
        company = db_session.query(Company).filter(Company.name.ilike(company_name)).first()
        # If found by name but it has no ticker, link the ticker now
        if company and ticker and not company.ticker:
            company.ticker = ticker
            db_session.commit()
            add_log(
                document.id,
                FinancialStatementMilestone.CLASSIFICATION,
                f"I've updated the ticker for {company.name} to {ticker}.",
            )

    # 3. Create new if still not found
    if not company:
        company = Company(id=str(uuid.uuid4()), name=company_name or ticker, ticker=ticker)
        db_session.add(company)
        db_session.commit()
        db_session.refresh(company)
        add_log(
            document.id,
            FinancialStatementMilestone.CLASSIFICATION,
            f"I've created a new entry for {company.name} in my database.",
        )

    if document:
        document.company_id = company.id
        document.document_type = classification_data.get("document_type")
        document.time_period = classification_data.get("time_period")
        document.period_end_date = classification_data.get("period_end_date")
        document.unique_id = document_hash
        document.page_count = total_pages
        document.character_count = character_count
        db_session.commit()

    document_type = classification_data.get("document_type")
    time_period = classification_data.get("time_period")
    duplicate_check = None

    if document_type:
        duplicate_check = check_duplicate_document(
            db=db_session,
            company_id=company.id,
            document_type=document_type,
            time_period=time_period,
            filename=resolved_filename,
            unique_id=document_hash,
            exclude_document_id=document_id,
        )

    if document and duplicate_check and duplicate_check.get("is_duplicate"):
        existing_doc = duplicate_check["existing_document"]
        document.duplicate_detected = True
        document.existing_document_id = existing_doc.id
        document.indexing_status = ProcessingStatus.CLASSIFYING
        db_session.commit()
        add_log(
            document.id,
            FinancialStatementMilestone.CLASSIFICATION,
            "I've detected that this document is a duplicate of one already in the system.",
        )
        return DocumentProcessingResult(
            classification_data=classification_data,
            duplicate_check=duplicate_check,
            summary=None,
            extracted_text_preview=extracted_text_preview,
            document_hash=document_hash,
            total_pages=total_pages,
            character_count=character_count,
            company=company,
        )

    # Check if document is an earnings announcement - only process those
    if mode != DocumentProcessingMode.PREVIEW and document:
        if document_type != DocumentType.EARNINGS_ANNOUNCEMENT:
            document.indexing_status = ProcessingStatus.CLASSIFIED
            db_session.commit()
            add_log(
                document.id,
                FinancialStatementMilestone.CLASSIFICATION,
                f"I'm skipping the full extraction because I currently only support earnings announcements (this is a {document_type}).",
            )
            return DocumentProcessingResult(
                classification_data=classification_data,
                duplicate_check=duplicate_check,
                summary=None,
                extracted_text_preview=extracted_text_preview,
                document_hash=document_hash,
                total_pages=total_pages,
                character_count=character_count,
                company=company,
            )

    summary = None
    try:
        if document:
            add_log(
                document.id,
                FinancialStatementMilestone.INDEX,
                "I'm asking Gemini to generate a concise summary of the entire document.",
            )

        summary = generate_document_summary(extracted_text)

        if summary and document:
            document.summary = summary
            db_session.commit()
            add_log(
                document.id,
                FinancialStatementMilestone.INDEX,
                "Gemini has finished generating the document summary.",
            )
    except Exception as exc:
        print(f"Warning: Failed to generate summary: {exc}")

    if mode == DocumentProcessingMode.PREVIEW:
        return DocumentProcessingResult(
            classification_data=classification_data,
            duplicate_check=duplicate_check,
            summary=summary,
            extracted_text_preview=extracted_text_preview,
            document_hash=document_hash,
            total_pages=total_pages,
            character_count=character_count,
            company=company,
        )

    # Shadowing status: Start Indexing
    update_milestone(
        document.id,
        FinancialStatementMilestone.INDEX,
        MilestoneStatus.IN_PROGRESS,
        message="I'm preparing the document for deep search by indexing its contents...",
    )

    document.indexing_status = ProcessingStatus.INDEXING
    db_session.commit()

    try:
        add_log(
            document.id, FinancialStatementMilestone.INDEX, "I'm starting the indexing process now."
        )
        index_document_chunks(resolved_file_path, document.id, chunk_size=chunk_size)
        add_log(
            document.id,
            FinancialStatementMilestone.INDEX,
            "The indexing process finished successfully.",
        )
    except Exception as e:
        add_log(
            document.id,
            FinancialStatementMilestone.INDEX,
            f"I ran into an error while indexing: {e}",
        )
        update_milestone(
            document.id,
            FinancialStatementMilestone.INDEX,
            MilestoneStatus.ERROR,
            message=f"Indexing failed: {str(e)}",
        )
        raise e

    _, total_pages, character_count = extract_text_from_pdf(resolved_file_path, max_pages=None)

    # Shadowing status: Indexing Success
    update_milestone(
        document.id,
        FinancialStatementMilestone.INDEX,
        MilestoneStatus.COMPLETED,
        message=f"Indexing complete! I've processed {total_pages} pages ({character_count} characters).",
    )

    document.indexing_status = ProcessingStatus.INDEXED
    document.indexed_at = datetime.utcnow()
    document.page_count = total_pages
    document.character_count = character_count
    db_session.commit()

    return DocumentProcessingResult(
        classification_data=classification_data,
        duplicate_check=duplicate_check,
        summary=summary,
        extracted_text_preview=extracted_text_preview,
        document_hash=document_hash,
        total_pages=total_pages,
        character_count=character_count,
        company=company,
    )
