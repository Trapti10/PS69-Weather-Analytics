"""
PS69 Weather Analytics - Phase 5: JWT Authentication Handler
Token generation, validation, and refresh logic
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import logging

from phase5.api.config import get_settings

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

settings = get_settings()


class JWTHandler:
    """JWT token handler."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def create_access_token(
        data: dict,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                hours=settings.JWT_EXPIRATION_HOURS
            )
        
        to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
        
        try:
            encoded_jwt = jwt.encode(
                to_encode,
                settings.JWT_SECRET,
                algorithm=settings.JWT_ALGORITHM
            )
            return encoded_jwt
        except Exception as e:
            logger.error(f"Error encoding JWT: {e}")
            raise
    
    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """Create a JWT refresh token."""
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRATION_DAYS
        )
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "refresh"
        })
        
        try:
            encoded_jwt = jwt.encode(
                to_encode,
                settings.JWT_SECRET,
                algorithm=settings.JWT_ALGORITHM
            )
            return encoded_jwt
        except Exception as e:
            logger.error(f"Error encoding refresh JWT: {e}")
            raise
    
    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except JWTError as e:
            logger.debug(f"JWT verification failed: {e}")
            return None
    
    @staticmethod
    def extract_user_id_from_token(token: str) -> Optional[str]:
        """Extract user_id from token."""
        payload = JWTHandler.verify_token(token)
        if payload:
            return payload.get("sub")
        return None
    
    @staticmethod
    def extract_role_from_token(token: str) -> Optional[str]:
        """Extract user role from token."""
        payload = JWTHandler.verify_token(token)
        if payload:
            return payload.get("role")
        return None


def create_tokens_for_user(user_id: str, email: str, role: str) -> dict:
    """Create both access and refresh tokens for a user."""
    access_token = JWTHandler.create_access_token(
        data={"sub": user_id, "email": email, "role": role}
    )
    refresh_token = JWTHandler.create_refresh_token(
        data={"sub": user_id, "email": email}
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_EXPIRATION_HOURS * 3600,  # seconds
    }
