"""
管理员配置与上帝模式相关的入口响应辅助。
"""

from typing import Any, Dict, List, Optional

import httpx


def build_admin_config_updated_response() -> Dict[str, Any]:
    """构建管理员配置更新成功响应。"""
    return {"success": True, "message": "配置已更新"}


def build_fetch_models_success_response(model_ids: List[str]) -> Dict[str, Any]:
    """构建远程模型拉取成功响应。"""
    return {
        "success": True,
        "models": model_ids,
        "model_ids": model_ids,
        "total": len(model_ids),
    }


def build_fetch_models_error_response(error: Exception) -> Dict[str, Any]:
    """构建远程模型拉取失败响应。"""
    if isinstance(error, ValueError):
        message = str(error)
    elif isinstance(error, httpx.HTTPStatusError):
        message = f"HTTP {error.response.status_code}: {error.response.text[:200]}"
    else:
        message = str(error)
    return {"success": False, "message": message}


def build_god_mode_verify_response(password: str, expected_password: Optional[str]) -> Dict[str, Any]:
    """构建上帝模式密码验证响应。"""
    if not expected_password:
        return {"success": False, "message": "本局游戏未启用上帝模式"}
    if password == expected_password:
        return {"success": True, "message": "验证成功"}
    return {"success": False, "message": "密码错误"}
