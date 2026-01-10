"""
SSE Endpoint for real-time document status updates.
"""

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.models.document import Document, DocumentStatus, ProcessingStatus

router = APIRouter()

# Config
POLL_INTERVAL = 2  # Seconds


@router.get("/status-stream")
async def status_stream(
    request: Request,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user), # Optional: Enforce auth if needed
):
    """
    Server-Sent Events (SSE) endpoint to stream document status updates.
    Client should connect to this endpoint and listen for 'status_update' events.
    """

    async def event_generator() -> AsyncGenerator[dict, None]:
        """
        Generator function to yield status updates.
        """
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                # Query active documents (not fully processed or error)
                # We define "Active" as anything not processed and not error.
                # OR we can just stream ALL recent documents?
                # Better: Stream documents that are "in progress".

                # We need a new session per iteration or be careful with session lifecycle in async gen
                # Ideally, we refrain from long-running DB sessions.
                # We'll use a fresh query each time.

                # Note: 'db' dependency is request-scoped. It might close if we await too long?
                # Actually, in FastAPI, the dependency stays alive until response finishes.
                # But for SSE, response is indefinite.
                # Safe to use `db` here? Yes, but refreshing objects is needed.

                # Active statuses
                active_statuses = [
                    ProcessingStatus.UPLOADING,
                    ProcessingStatus.PENDING,
                    ProcessingStatus.CLASSIFYING,
                    ProcessingStatus.INDEXING,
                    ProcessingStatus.PROCESSING,
                ]

                # Query DB
                # We might want to filter by user if we enforce auth
                documents = (
                    db.query(Document)
                    .filter(
                        Document.analysis_status.in_(active_statuses)
                        | Document.indexing_status.in_(active_statuses)
                        | (Document.status != DocumentStatus.PROCESSING_COMPLETE)
                        & (Document.status != DocumentStatus.EXTRACTION_FAILED)
                        & (Document.status != DocumentStatus.CLASSIFICATION_FAILED)
                        & (Document.status != DocumentStatus.UPLOAD_FAILED)
                    )
                    .all()
                )

                if documents:
                    data = []
                    for doc in documents:
                        data.append(
                            {
                                "document_id": doc.id,
                                "filename": doc.filename,
                                "status": doc.status,  # The new unified status
                                "indexing_status": doc.indexing_status,
                                "analysis_status": doc.analysis_status,
                                "updated_at": str(doc.processed_at or doc.uploaded_at),
                            }
                        )

                    # Yield event
                    yield {"event": "status_update", "data": json.dumps(data)}
                else:
                    # Send keep-alive or empty list?
                    # Empty list helps frontend know nothing is happening.
                    yield {"event": "status_update", "data": json.dumps([])}

                await asyncio.sleep(POLL_INTERVAL)

                # Refresh db session to see new updates?
                # Actually, `db.query` checks the current state, but SQLAlchemy identity map might cache.
                # We should expire_all to force reload from DB.
                db.expire_all()

        except asyncio.CancelledError:
            pass

    return EventSourceResponse(event_generator())
