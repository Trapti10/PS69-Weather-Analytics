"""
PS69 Weather Analytics - Phase 5: Authentication Routes
POST /auth/login, POST /auth/register, POST /auth/refresh
"""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
import logging

from phase5.api.models import User
from phase5.api.schemas import UserRegisterRequest, UserLoginRequest, TokenResponse
from phase5.api.db import get_db
from phase5.api.auth.jwt_handler import JWTHandler, create_tokens_for_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/register", response_model=TokenResponse)
def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user.
    
    Synchronous processing:
    - Validate input
    - Hash password
    - Create user in PostgreSQL
    - Return tokens immediately
    """
    # Check if user already exists
    existing_user = db.execute(
        select(User).where(User.email == request.email)
    ).scalars().first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    try:
        # Hash password
        hashed_password = JWTHandler.hash_password(request.password)
        
        # Create user
        # Public registration is intentionally restricted to CITIZEN accounts.
        # Analyst/Admin roles must be provisioned by an operator/seed process.
        new_user = User(
            email=request.email,
            password_hash=hashed_password,
            role="CITIZEN"
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"User registered: {new_user.email} (role: {new_user.role})")
        
        # Create tokens
        tokens = create_tokens_for_user(
            user_id=str(new_user.user_id),
            email=new_user.email,
            role=new_user.role
        )
        
        return TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            user_id=new_user.user_id,
            role=new_user.role,
            expires_in=tokens["expires_in"]
        )
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error registering user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error during registration"
        )


@router.post("/login", response_model=TokenResponse)
def login(
    request: UserLoginRequest,
    db: Session = Depends(get_db)
):
    """
    User login.
    
    Synchronous processing:
    - Look up user by email
    - Verify password
    - Return tokens immediately
    """
    # Find user
    user = db.execute(
        select(User).where(User.email == request.email)
    ).scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not JWTHandler.verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    try:
        # Update last login
        from datetime import datetime
        user.last_login = datetime.utcnow()
        db.commit()
        
        logger.info(f"User logged in: {user.email}")
        
        # Create tokens
        tokens = create_tokens_for_user(
            user_id=str(user.user_id),
            email=user.email,
            role=user.role
        )
        
        return TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            user_id=user.user_id,
            role=user.role,
            expires_in=tokens["expires_in"]
        )
    
    except Exception as e:
        logger.error(f"Error during login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error during login"
        )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.
    
    Synchronous processing:
    - Verify refresh token
    - Look up user
    - Return new access token + refresh token
    """
    payload = JWTHandler.verify_token(refresh_token)
    
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    user_id = payload.get("sub")
    
    try:
        # Look up user
        user = db.execute(
            select(User).where(User.user_id == user_id)
        ).scalars().first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        logger.info(f"Token refreshed for user: {user.email}")
        
        # Create new tokens
        tokens = create_tokens_for_user(
            user_id=str(user.user_id),
            email=user.email,
            role=user.role
        )
        
        return TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            user_id=user.user_id,
            role=user.role,
            expires_in=tokens["expires_in"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error refreshing token"
        )
