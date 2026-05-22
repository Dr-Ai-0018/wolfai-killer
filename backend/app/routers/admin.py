"""
Admin API routes with authentication
"""
from typing import Optional
import httpx
from fastapi import APIRouter, Depends, HTTPException
from dotenv import set_key
import os

from ..core.config import settings
from ..core.security import require_admin_auth, verify_admin_password
from ..models.schemas import AdminConfigUpdate, FetchModelsRequest, AdminLoginRequest

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Session storage (in production, use Redis or database)
admin_sessions = set()


@router.post("/login")
async def admin_login(request: AdminLoginRequest):
    """Admin login - returns session token if password correct"""
    if not settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=503, detail="管理员密码未配置，请在.env中设置WEREWOLF_ADMIN_PASSWORD")
    
    if not verify_admin_password(request.password):
        raise HTTPException(status_code=403, detail="密码错误")
    
    return {"success": True, "message": "登录成功"}


@router.get("/config")
async def get_admin_config(_: bool = Depends(require_admin_auth)):
    """获取当前配置（脱敏）"""
    return {
        "api_url": settings.API_BASE_URL,
        "api_key_masked": "***" + settings.API_KEY[-4:] if settings.API_KEY else "",
        "models": settings.MODELS,
        "default_timeout": settings.DEFAULT_TIMEOUT,
        "model_timeout_map": settings.MODEL_TIMEOUT_MAP,
    }


@router.post("/config")
async def update_admin_config(request: AdminConfigUpdate, _: bool = Depends(require_admin_auth)):
    """更新配置"""
    env_path = settings.BASE_DIR / ".env"
    
    # 更新 .env 文件
    if request.api_url:
        set_key(str(env_path), "WEREWOLF_API_BASE_URL", request.api_url)
        settings.API_BASE_URL = request.api_url
    
    if request.api_key:
        set_key(str(env_path), "WEREWOLF_API_KEY", request.api_key)
        settings.API_KEY = request.api_key
    
    # 更新 config.yaml 中的 models
    if request.models is not None:
        settings.MODELS = request.models
        settings.save_to_yaml({"models": request.models})
    
    return {"success": True, "message": "配置已更新"}


@router.post("/fetch-models")
async def fetch_remote_models(request: FetchModelsRequest, _: bool = Depends(require_admin_auth)):
    """从远程API获取模型列表"""
    try:
        models_url = request.api_url.rstrip('/') + '/models'
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                models_url,
                headers={
                    "Authorization": f"Bearer {request.api_key}",
                    "Content-Type": "application/json"
                }
            )
            resp.raise_for_status()
            data = resp.json()
        
        # 解析模型数据 - 兼容多种格式
        models_array = []
        if isinstance(data, dict):
            if "data" in data:
                inner_data = data["data"]
                if isinstance(inner_data, dict) and "data" in inner_data and isinstance(inner_data["data"], list):
                    models_array = inner_data["data"]
                elif isinstance(inner_data, list):
                    models_array = inner_data
            elif isinstance(data.get("models"), list):
                models_array = data["models"]
        elif isinstance(data, list):
            models_array = data
        
        # 提取模型ID
        model_ids = []
        for model in models_array:
            if isinstance(model, dict) and "id" in model:
                model_ids.append(model["id"])
            elif isinstance(model, str):
                model_ids.append(model)
        
        return {
            "success": True,
            "models": model_ids,
            "total": len(model_ids)
        }
    except httpx.HTTPStatusError as e:
        return {"success": False, "message": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/check")
async def check_admin_status():
    """Check if admin password is configured"""
    return {
        "configured": bool(settings.ADMIN_PASSWORD),
        "message": "管理员密码已配置" if settings.ADMIN_PASSWORD else "请在.env中设置WEREWOLF_ADMIN_PASSWORD"
    }
