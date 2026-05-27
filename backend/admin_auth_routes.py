"""
管理员认证相关入口响应辅助。
"""

from datetime import datetime
from typing import Any, Dict


def build_admin_check_payload(admin_password: str | None) -> Dict[str, Any]:
    """构建管理员是否已配置的响应。"""
    configured = bool(admin_password)
    return {
        "configured": configured,
        "message": "管理员密码已配置" if configured else "请在.env中设置WEREWOLF_ADMIN_PASSWORD",
    }


def build_admin_login_success_payload(token_data: Dict[str, Any]) -> Dict[str, Any]:
    """构建管理员登录成功响应。"""
    return {
        "success": True,
        "message": "登录成功",
        **token_data,
    }


def build_admin_refresh_payload(token_data: Dict[str, Any]) -> Dict[str, Any]:
    """构建管理员凭证刷新成功响应。"""
    return {
        "success": True,
        "message": "登录凭证已刷新",
        **token_data,
    }


def build_admin_verify_payload(admin: Dict[str, Any]) -> Dict[str, Any]:
    """构建管理员 token 校验成功响应。"""
    return {
        "valid": True,
        "admin": admin.get("sub"),
        "expires_at": datetime.fromtimestamp(admin.get("exp", 0)).isoformat(),
    }
