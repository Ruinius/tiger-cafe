"""
SSE Endpoint for real-time document status updates.
"""

import asyncio
import json
import os
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database import SessionLocal, get_db
from app.models.document import Document, DocumentStatus
from app.models.user import User
from app.utils.financial_statement_progress import get_progress_with_db_fallback
from config.config import ALGORITHM, SECRET_KEY

router = APIRouter()
security = HTTPBearer(auto_error=False)

# Config
POLL_INTERVAL = 2  # Seconds


async def verify_token_from_query(token: str | None, db: Session) -> User | None:
    """Verify token from query parameter and return user."""
    if not token:
        return None

    # Check for mock environment or dev token
    if (
        os.environ.get("MOCK_LLM_RESPONSES") == "true" and token == "fake-token"
    ) or token == "dev-token":
        email = "dev@example.com"
        user = db.query(User).filter(User.email == email).first()
        if not user:
            # Create dev user if missing (fallback, though seeder should handle this)
            user = User(
                id=email, email=email, first_name="Dev", last_name="User", auth_provider="local"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    try:
        # Verify App Token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None

        user = db.query(User).filter(User.email == email).first()
        return user
    except JWTError as e:
        print(f"[SSE] Token verification failed: {e}")
        return None


@router.get("/status-stream")
async def status_stream(
    request: Request,
    token: str
    | None = None,  # Token passed as query param since EventSource doesn't support headers
    db: Session = Depends(get_db),
):
    """
    Server-Sent Events (SSE) endpoint to stream document status updates.
    Client should connect to this endpoint and listen for 'status_update' events.

    Authentication is optional but recommended. Pass token as query parameter.
    """

    # Verify token and get user
    current_user = await verify_token_from_query(token, db)

    # Extract user ID early to avoid dependency on the outer session
    current_user_id = current_user.id if current_user else None

    async def event_generator() -> AsyncGenerator[dict, None]:
        """
        Generator function to yield status updates.
        """
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                # Use a fresh session for each poll to ensure data is fresh and session is healthy
                with SessionLocal() as stream_db:
                    # Query active documents AND recently completed ones (for UI retention)
                    from datetime import datetime, timedelta

                    terminal_statuses = [
                        DocumentStatus.PROCESSING_COMPLETE,
                        DocumentStatus.CLASSIFIED,
                        DocumentStatus.EXTRACTION_FAILED,
                        DocumentStatus.CLASSIFICATION_FAILED,
                        DocumentStatus.INDEXING_FAILED,
                        DocumentStatus.UPLOAD_FAILED,
                    ]

                    # Get active (non-terminal) documents
                    active_query = stream_db.query(Document).filter(
                        ~Document.status.in_(terminal_statuses)
                    )

                    # Get recently completed documents (within last 60 seconds)
                    recent_cutoff = datetime.utcnow() - timedelta(seconds=60)
                    completed_query = stream_db.query(Document).filter(
                        Document.status.in_(terminal_statuses),
                        Document.processed_at >= recent_cutoff,
                    )

                    # Filter by user if authenticated
                    if current_user_id:
                        active_query = active_query.filter(Document.user_id == current_user_id)
                        completed_query = completed_query.filter(
                            Document.user_id == current_user_id
                        )

                    # Combine active and recently completed
                    active_docs = active_query.all()
                    completed_docs = completed_query.all()
                    documents = active_docs + completed_docs

                    if documents:
                        data = []
                        for doc in documents:
                            data.append(
                                {
                                    "id": doc.id,
                                    "filename": doc.filename,
                                    "status": doc.status,
                                    "current_step": doc.current_step,
                                    "indexing_status": doc.indexing_status,
                                    "analysis_status": doc.analysis_status,
                                    "duplicate_detected": doc.duplicate_detected,
                                    "existing_document_id": doc.existing_document_id,
                                    "updated_at": str(doc.processed_at or doc.uploaded_at),
                                    "financial_statement_progress": get_progress_with_db_fallback(
                                        doc.id, stream_db
                                    ),
                                }
                            )

                        # Yield event
                        yield {"event": "status_update", "data": json.dumps(data)}
                    else:
                        # Send empty list to indicate no active documents
                        yield {"event": "status_update", "data": json.dumps([])}

                await asyncio.sleep(POLL_INTERVAL)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[SSE] Error in event generator: {e}")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())
