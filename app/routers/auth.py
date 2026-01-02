"""
Authentication routes (Google OAuth)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import User as UserSchema
import google.auth.transport.requests
import google.oauth2.id_token
from config.config import GOOGLE_CLIENT_ID

router = APIRouter()
security = HTTPBearer()


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify Google ID token and return user info"""
    try:
        request = google.auth.transport.requests.Request()
        id_token = credentials.credentials
        
        # Verify the token
        id_info = google.oauth2.id_token.verify_oauth2_token(
            id_token, request, GOOGLE_CLIENT_ID
        )
        
        if id_info["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Wrong issuer")
        
        return id_info
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {str(e)}"
        )


async def get_current_user(
    id_info: dict = Depends(verify_token),
    db: Session = Depends(get_db)
) -> User:
    """Get or create current user from Google ID token"""
    user_id = id_info["sub"]
    email = id_info["email"]
    name = id_info.get("name")
    picture = id_info.get("picture")
    
    # Get or create user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        user = User(
            id=user_id,
            email=email,
            name=name,
            picture=picture
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update user info
        user.email = email
        user.name = name
        user.picture = picture
        db.commit()
        db.refresh(user)
    
    return user


@router.get("/me", response_model=UserSchema)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user info"""
    return current_user


@router.post("/login")
async def login(id_info: dict = Depends(verify_token)):
    """Login endpoint - returns user info after token verification"""
    return {
        "message": "Login successful",
        "user_id": id_info["sub"],
        "email": id_info["email"]
    }

