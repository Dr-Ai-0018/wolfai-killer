"""
月夜狼人杀后端应用
基于 WebSocket 的实时对局服务
"""

import os
import json
import asyncio
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv, set_key
import httpx
import secrets

from app_manager import GameManager, normalize_model_ids
from admin_auth import create_admin_token, get_admin_password, verify_token
from admin_auth_routes import (
    build_admin_check_payload,
    build_admin_login_success_payload,
    build_admin_refresh_payload,
    build_admin_verify_payload,
)
from app_create import build_create_game_response, build_game_setup_kwargs, resolve_god_mode_password
from app_game_control import (
    pause_game_response,
    resume_game_response,
    start_game_response,
    submit_action_response,
)
from app_game_read import (
    get_game_log_response,
    get_game_player_view_response,
    get_game_players_response,
    get_game_status_response,
)
from admin_config import fetch_remote_model_ids, normalize_openai_v1_base_url, update_admin_config_state
from admin_routes import (
    build_admin_config_updated_response,
    build_fetch_models_error_response,
    build_fetch_models_success_response,
    build_god_mode_verify_response,
)
from app_readonly import (
    build_admin_config_payload,
    build_model_catalog,
    build_stats_overview_payload,
    get_stats_game_detail_or_404,
)
from app_requests import (
    ActionRequest,
    AdminConfigUpdate,
    AdminLoginRequest,
    CreateGameRequest,
    FetchModelsRequest,
    GodModeVerifyRequest,
    validate_role_balance,
)
from game_stats import stats_manager
from game_views import (
    build_phantom_actions_payload,
    get_engine_or_404,
    verify_god_mode_access,
)
from game_ws import build_connected_payload, build_missing_game_payload, handle_websocket_message

# Load environment variables
load_dotenv()

game_manager = GameManager(os.path.dirname(__file__))


# ========== Lifespan ==========

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("正在启动月夜狼人杀服务...")
    game_manager.load_config()
    print("配置已加载")
    print("月夜狼人杀服务已启动")
    yield
    print("月夜狼人杀服务正在关闭...")


# ========== FastAPI App ==========

app = FastAPI(
    title="月夜狼人杀接口",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for emojis
emojis_path = os.path.join(os.path.dirname(__file__), "Emojis")
if os.path.exists(emojis_path):
    app.mount("/emojis", StaticFiles(directory=emojis_path), name="emojis")


# ========== REST Endpoints ==========

@app.get("/")
async def root():
    return {"name": "月夜狼人杀接口", "version": "2.0.0"}


@app.get("/api/config/roles")
async def get_roles():
    """Get available roles"""
    roles_path = os.path.join(os.path.dirname(__file__), "data", "roles.json")
    try:
        with open(roles_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 返回 roles 数组
            return data.get("roles", data) if isinstance(data, dict) else data
    except:
        return []


@app.get("/api/config/personalities")
async def get_personalities():
    """Get available personalities"""
    from game_engine import PERSONALITIES
    return [{"code": p.code, "name": p.name, "description": p.description} for p in PERSONALITIES]


@app.get("/api/config/models")
async def get_models():
    """Get available AI models"""
    return build_model_catalog(game_manager.config.get("models", []), normalize_model_ids)


@app.get("/api/stats/overview")
async def get_stats():
    """获取总览统计"""
    return build_stats_overview_payload(stats_manager.get_overview(), game_manager.games.values())


@app.get("/api/stats/detailed")
async def get_detailed_stats():
    """获取详细统计数据"""
    return stats_manager.get_detailed_stats()


@app.get("/api/stats/roles")
async def get_role_stats():
    """获取角色统计"""
    return stats_manager.get_role_stats()


@app.get("/api/stats/personalities")
async def get_personality_stats():
    """获取人格统计"""
    return stats_manager.get_personality_stats()


@app.get("/api/stats/models")
async def get_model_stats():
    """获取模型统计"""
    return stats_manager.get_model_stats()


@app.get("/api/stats/history")
async def get_history(page: int = 1, per_page: int = 20):
    """获取历史记录"""
    return stats_manager.get_history(page, per_page)


@app.get("/api/stats/game/{game_id}")
async def get_game_detail(game_id: str):
    """获取单局游戏详情"""
    return get_stats_game_detail_or_404(stats_manager, game_id)


@app.post("/api/game/create")
async def create_game(request: CreateGameRequest):
    """Create a new game"""
    validate_role_balance(request.total_players, request.role_config, request.num_wolves)
    god_mode_password = resolve_god_mode_password(request.god_mode)
    
    engine = game_manager.create_game(
        human_seats=request.human_seats,
        total_players=request.total_players,
        num_wolves=request.num_wolves,
        role_config=request.role_config,
        god_mode_password=god_mode_password
    )
    
    avatars = game_manager.get_avatars()
    await engine.setup(**build_game_setup_kwargs(request, avatars))

    return build_create_game_response(engine)


@app.get("/api/game/{game_id}/status")
async def get_game_status(game_id: str):
    """Get game status"""
    return get_game_status_response(game_manager, game_id)


@app.get("/api/game/{game_id}/players")
async def get_players(game_id: str):
    """Get players list"""
    return get_game_players_response(game_manager, game_id)


@app.get("/api/game/{game_id}/player/{seat}")
async def get_player_view(game_id: str, seat: int):
    """Get player's private view"""
    return get_game_player_view_response(game_manager, game_id, seat)


@app.get("/api/game/{game_id}/log")
async def get_game_log(game_id: str, offset: int = 0, limit: int = 100):
    """Get game logs"""
    return get_game_log_response(game_manager, game_id, offset, limit)


@app.post("/api/game/{game_id}/start")
async def start_game(game_id: str):
    """Start the game"""
    return await start_game_response(game_manager, game_id, asyncio.create_task)


@app.post("/api/game/{game_id}/pause")
async def pause_game(game_id: str):
    """Pause the game"""
    return pause_game_response(game_manager, game_id)


@app.post("/api/game/{game_id}/resume")
async def resume_game(game_id: str):
    """Resume the game"""
    return resume_game_response(game_manager, game_id)


@app.post("/api/game/{game_id}/action")
async def submit_action(game_id: str, request: ActionRequest):
    """Submit human player action (REST fallback)"""
    return submit_action_response(game_manager, game_id, request.data)


# ========== JWT Authentication ==========

# Security scheme
security = HTTPBearer(auto_error=False)

async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to verify admin JWT token"""
    if not credentials:
        raise HTTPException(status_code=401, detail="需要登录认证")
    
    payload = verify_token(credentials.credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    
    return payload


# ========== Admin API ==========

@app.get("/api/admin/check")
async def check_admin_status():
    """Check if admin password is configured"""
    return build_admin_check_payload(get_admin_password())


@app.post("/api/admin/login")
async def admin_login(request: AdminLoginRequest):
    """Admin login - returns JWT token"""
    admin_pwd = get_admin_password()
    if not admin_pwd:
        raise HTTPException(status_code=503, detail="管理员密码未配置，请在.env中设置WEREWOLF_ADMIN_PASSWORD")
    
    if secrets.compare_digest(request.password, admin_pwd):
        return build_admin_login_success_payload(create_admin_token())
    
    raise HTTPException(status_code=403, detail="密码错误")


@app.post("/api/admin/refresh")
async def refresh_admin_token(admin: dict = Depends(get_current_admin)):
    """Refresh JWT token"""
    return build_admin_refresh_payload(create_admin_token())


@app.get("/api/admin/verify")
async def verify_admin_token(admin: dict = Depends(get_current_admin)):
    """Verify current token is valid"""
    return build_admin_verify_payload(admin)


@app.get("/api/admin/config")
async def get_admin_config(_: dict = Depends(get_current_admin)):
    """获取当前配置（脱敏）"""
    return build_admin_config_payload(game_manager.config, normalize_model_ids)


@app.post("/api/admin/config")
async def update_admin_config(request: AdminConfigUpdate, _: dict = Depends(get_current_admin)):
    """更新配置"""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    requested_model_ids = request.model_ids if request.model_ids is not None else request.models
    update_admin_config_state(
        game_config=game_manager.config,
        env_path=env_path,
        config_path=config_path,
        api_url=request.api_url,
        api_key=request.api_key,
        requested_model_ids=requested_model_ids,
        normalize_model_ids=normalize_model_ids,
        set_key_fn=set_key,
    )

    return build_admin_config_updated_response()


@app.post("/api/admin/fetch-models")
async def fetch_remote_models(request: FetchModelsRequest, _: dict = Depends(get_current_admin)):
    """从远程API获取模型列表"""
    try:
        model_ids = await fetch_remote_model_ids(
            api_config=game_manager.config.get("api", {}),
            api_url=request.api_url,
            api_key=request.api_key,
            async_client_cls=httpx.AsyncClient,
        )
        return build_fetch_models_success_response(model_ids)
    except ValueError as e:
        return build_fetch_models_error_response(e)
    except httpx.HTTPStatusError as e:
        return build_fetch_models_error_response(e)
    except Exception as e:
        return build_fetch_models_error_response(e)


@app.post("/api/game/{game_id}/god-mode/verify")
async def verify_god_mode(game_id: str, request: GodModeVerifyRequest):
    """验证上帝模式密码"""
    engine = get_engine_or_404(game_manager, game_id)
    return build_god_mode_verify_response(request.password, engine.god_mode_password)


@app.get("/api/game/{game_id}/god-mode/logs")
async def get_god_mode_logs(game_id: str, password: str, offset: int = 0, limit: int = 100):
    """获取上帝模式日志（包含所有私密信息）"""
    engine = get_engine_or_404(game_manager, game_id)
    verify_god_mode_access(engine, password)
    return {"logs": engine.logs[offset:offset+limit], "total": len(engine.logs)}


@app.get("/api/game/{game_id}/god-mode/players")
async def get_god_mode_players(game_id: str, password: str):
    """获取所有玩家的完整信息（包括身份）"""
    engine = get_engine_or_404(game_manager, game_id)
    verify_god_mode_access(engine, password)
    return [p.to_private_dict() for p in engine.players.values()]


@app.get("/api/game/{game_id}/phantom-actions")
async def get_phantom_actions(game_id: str):
    """获取冥界复盘数据 - 死亡角色的虚拟行动记录（仅游戏结束后可见）"""
    engine = get_engine_or_404(game_manager, game_id)
    return build_phantom_actions_payload(engine)


# ========== WebSocket Endpoint ==========

@app.websocket("/ws/{game_id}/{seat}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, seat: int):
    """WebSocket connection for real-time game updates"""
    await websocket.accept()
    
    engine = game_manager.get_game(game_id)
    if not engine:
        await websocket.send_json(build_missing_game_payload())
        await websocket.close()
        return
    
    # Register connection
    game_manager.add_connection(game_id, seat, websocket)
    
    # Send initial state
    player = engine.players.get(seat)
    if player:
        await websocket.send_json(build_connected_payload(engine, seat, player))
    
    try:
        while True:
            data = await websocket.receive_json()
            response = handle_websocket_message(engine, seat, data)
            if response is not None:
                await websocket.send_json(response)
    
    except WebSocketDisconnect:
        game_manager.remove_connection(game_id, seat)
    except Exception as e:
        print(f"实时通道错误：{e}")
        game_manager.remove_connection(game_id, seat)


# ========== Main ==========

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
