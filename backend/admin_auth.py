"""
管理员认证与 JWT 辅助逻辑。
"""

import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Optional

import jwt
from dotenv import set_key
from fastapi import HTTPException


JWT_ALGORITHM = "HS256"


def get_backend_env_path() -> str:
    """返回后端 .env 文件路径。"""
    return os.path.join(os.path.dirname(__file__), ".env")


def get_jwt_secret(env_path: Optional[str] = None) -> str:
    """获取 JWT 密钥；未配置时自动生成并写入 .env。"""
    secret = os.getenv("WEREWOLF_JWT_SECRET")
    if secret:
        return secret

    generated = secrets.token_urlsafe(32)
    target_env_path = env_path or get_backend_env_path()
    try:
        set_key(target_env_path, "WEREWOLF_JWT_SECRET", generated)
    except Exception:
        pass
    os.environ["WEREWOLF_JWT_SECRET"] = generated
    return generated


def get_jwt_expiry_hours() -> int:
    """获取管理员令牌过期小时数。"""
    try:
        return int(os.getenv("WEREWOLF_JWT_EXPIRY_HOURS", "24"))
    except ValueError:
        return 24


def get_admin_password() -> str:
    """获取管理员密码。"""
    return os.getenv("WEREWOLF_ADMIN_PASSWORD", "")


def create_admin_token() -> dict:
    """创建管理员 JWT 令牌。"""
    issued_at = datetime.now(UTC)
    expiry = issued_at + timedelta(hours=get_jwt_expiry_hours())
    payload = {
        "sub": "admin",
        "role": "admin",
        "exp": expiry,
        "iat": issued_at,
    }
    token = jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expiry.isoformat(),
        "expires_in": get_jwt_expiry_hours() * 3600,
    }


def verify_token(token: str) -> dict:
    """校验 JWT 并返回 payload。"""
    try:
        return jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登录凭证已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="登录凭证无效")
