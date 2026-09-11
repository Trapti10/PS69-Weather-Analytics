"""
PS69 Weather Analytics - Phase 5: Role-Based Access Control
Decorators and dependencies for endpoint authorization
"""

from fastapi import HTTPException, status, Depends, Request
from functools import wraps
from typing import Optional, Callable
import logging

from api.auth.jwt_handler import JWTHandler

logger = logging.getLogger(__name__)


class RoleChecker:
    """Check user role for endpoint authorization."""
    
    def __init__(self, allowed_roles: list):
        """Initialize with allowed roles."""
        self.allowed_roles = allowed_roles
    
    def __call__(self, request: Request) -> dict:
        """Check if user has required role."""
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization header",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        token = auth_header[7:]  # Remove "Bearer "
        
        # Verify token
        payload = JWTHandler.verify_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user_id = payload.get("sub")
        role = payload.get("role")
        email = payload.get("email")
        
        if not user_id or not role or not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        
        # Check role
        if role not in self.allowed_roles:
            logger.warning(f"User {user_id} with role {role} denied access (requires {self.allowed_roles})")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{role}' does not have permission to access this resource. Required: {self.allowed_roles}",
            )
        
        return {
            "user_id": user_id,
            "email": email,
            "role": role,
        }


# Pre-built role checkers
require_citizen = RoleChecker(allowed_roles=["CITIZEN", "ANALYST", "ADMIN"])
require_analyst = RoleChecker(allowed_roles=["ANALYST", "ADMIN"])
require_admin = RoleChecker(allowed_roles=["ADMIN"])


def require_role(*allowed_roles):
    """Decorator to require specific roles."""
    checker = RoleChecker(allowed_roles=list(allowed_roles))
    return Depends(checker)


def get_current_user(request: Request) -> dict:
    """Dependency: Get current user from token (any authenticated user)."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header[7:]
    payload = JWTHandler.verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    
    return {
        "user_id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role"),
    }

