"""
Authentication decorators for optional authentication support.
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user, verify_token

security = HTTPBearer(auto_error=False)


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User | None:
    """
    Get current user if authenticated, otherwise return None.
    This allows endpoints to work with or without authentication.

    Args:
        credentials: Optional HTTP bearer token
        db: Database session

    Returns:
        User object if authenticated, None otherwise
    """
    if not credentials:
        return None

    try:
        # Verify token
        id_info = await verify_token(credentials)
        # Get or create user
        current_user = await get_current_user(id_info, db)
        return current_user
    except HTTPException:
        # If auth fails, return None instead of raising exception
        return None
    except Exception as e:
        # Log error but don't fail the request
        print(f"[OptionalAuth] Authentication failed: {e}")
        return None
