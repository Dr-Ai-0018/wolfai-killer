"""
Security utilities for admin authentication
"""
import hashlib
import secrets
from typing import Optional
from fastapi import HTTPException, Depends, Header

from .config import settings


def get_admin_password_hash(password: str) -> str:
    """Hash admin password"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_admin_password(password: str) -> bool:
    """Verify admin password"""
    if not settings.ADMIN_PASSWORD:
        # No password configured - deny access
        return False
    return secrets.compare_digest(password, settings.ADMIN_PASSWORD)


async def require_admin_auth(x_admin_password: Optional[str] = Header(None, alias="X-Admin-Password")):
    """Dependency to require admin authentication"""
    if not x_admin_password:
        raise HTTPException(status_code=401, detail="需要管理员密码")
    
    if not verify_admin_password(x_admin_password):
        raise HTTPException(status_code=403, detail="管理员密码错误")
    
    return True


def generate_session_token() -> str:
    """Generate a secure session token"""
    return secrets.token_urlsafe(32)
