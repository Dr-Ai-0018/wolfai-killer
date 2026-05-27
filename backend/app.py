"""
月夜狼人杀后端应用
基于 WebSocket 的实时对局服务
"""

import os
import json
import asyncio
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv, set_key
import yaml
import httpx
import secrets

from admin_auth import create_admin_token, get_admin_password, verify_token
from admin_auth_routes import (
    build_admin_check_payload,
    build_admin_login_success_payload,
    build_admin_refresh_payload,
    build_admin_verify_payload,
)
from app_create import build_create_game_response, build_game_setup_kwargs, resolve_god_mode_password
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
from game_control import build_success_response, submit_waiting_human_action
from game_engine import GameEngine
from game_stats import stats_manager
from game_views import (
    build_game_status_payload,
    build_phantom_actions_payload,
    build_public_logs_payload,
    get_engine_or_404,
    get_player_or_404,
    verify_god_mode_access,
)
from game_ws import build_connected_payload, build_missing_game_payload, handle_websocket_message

# Load environment variables
load_dotenv()


def normalize_model_ids(raw_models: Any) -> List[str]:
    """Normalize configured models into a unique list of model ids."""
    if not isinstance(raw_models, list):
        return []

    model_ids: List[str] = []
    for item in raw_models:
        model_id = ""
        if isinstance(item, str):
            model_id = item.strip()
        elif isinstance(item, dict):
            candidate = item.get("id") or item.get("name") or item.get("model") or item.get("value")
            if isinstance(candidate, str):
                model_id = candidate.strip()

        if model_id and model_id not in model_ids:
            model_ids.append(model_id)

    return model_ids


def parse_model_timeout_overrides(raw: Optional[str]) -> Dict[str, int]:
    """Parse env overrides like 'gpt-5.4-mini=15,gpt-5.4=20'."""
    if not raw:
        return {}

    overrides: Dict[str, int] = {}
    for chunk in raw.split(","):
        item = chunk.strip()
        if not item or "=" not in item:
            continue
        model_name, timeout_value = item.split("=", 1)
        model_name = model_name.strip()
        timeout_value = timeout_value.strip()
        if not model_name or not timeout_value:
            continue
        try:
            overrides[model_name] = int(timeout_value)
        except ValueError:
            continue
    return overrides


# ========== Game Manager ==========

class GameManager:
    def __init__(self):
        self.games: Dict[str, GameEngine] = {}
        self.connections: Dict[str, Dict[int, WebSocket]] = {}  # game_id -> {seat -> ws}
        self.config: Dict[str, Any] = {}
    
    def load_config(self):
        """Load configuration"""
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            print(f"加载配置失败：{e}")
            self.config = {}
        
        # Override with environment variables
        if "api" not in self.config:
            self.config["api"] = {}
        
        api_key = os.getenv("WEREWOLF_API_KEY")
        if api_key:
            self.config["api"]["api_key"] = api_key
        
        base_url = os.getenv("WEREWOLF_API_BASE_URL")
        if base_url:
            self.config["api"]["base_url"] = base_url

        default_timeout = os.getenv("WEREWOLF_API_DEFAULT_TIMEOUT")
        if default_timeout:
            try:
                self.config["api"]["default_timeout"] = int(default_timeout)
            except ValueError:
                pass

        model_timeout_overrides = parse_model_timeout_overrides(os.getenv("WEREWOLF_API_MODEL_TIMEOUTS"))
        if model_timeout_overrides:
            existing = self.config["api"].get("model_timeout_map", {})
            if not isinstance(existing, dict):
                existing = {}
            existing = {**existing, **model_timeout_overrides}
            self.config["api"]["model_timeout_map"] = existing

        self.config["models"] = normalize_model_ids(self.config.get("models", []))
    
    def get_avatars(self) -> List[str]:
        """Get list of avatar files"""
        emojis_dir = os.path.join(os.path.dirname(__file__), "Emojis")
        if os.path.exists(emojis_dir):
            return [f for f in os.listdir(emojis_dir) if f.endswith('.webp')]
        return []
    
    def create_game(self, human_seats: List[int], total_players: int = 12, num_wolves: int = 3, 
                    role_config: Dict[str, int] = None, god_mode_password: Optional[str] = None) -> GameEngine:
        """Create a new game"""
        from datetime import datetime
        import uuid
        
        game_id = f"game_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        engine = GameEngine(game_id, self.config, god_mode_password=god_mode_password)
        
        # Set broadcast callback
        async def broadcast(event: str, data: Dict, to_seat: Optional[int] = None):
            await self.broadcast_to_game(game_id, event, data, to_seat)
        
        engine.set_broadcast(broadcast)
        self.games[game_id] = engine
        self.connections[game_id] = {}
        
        return engine
    
    async def broadcast_to_game(self, game_id: str, event: str, data: Dict, to_seat: Optional[int] = None):
        """Broadcast message to game connections"""
        if game_id not in self.connections:
            return
        
        message = json.dumps({"event": event, "data": data})
        
        if to_seat is not None:
            # Send to specific seat
            ws = self.connections[game_id].get(to_seat)
            if ws:
                try:
                    await ws.send_text(message)
                except:
                    pass
        else:
            # Broadcast to all
            for ws in self.connections[game_id].values():
                try:
                    await ws.send_text(message)
                except:
                    pass
    
    def get_game(self, game_id: str) -> Optional[GameEngine]:
        return self.games.get(game_id)
    
    def add_connection(self, game_id: str, seat: int, ws: WebSocket):
        if game_id not in self.connections:
            self.connections[game_id] = {}
        self.connections[game_id][seat] = ws
    
    def remove_connection(self, game_id: str, seat: int):
        if game_id in self.connections and seat in self.connections[game_id]:
            del self.connections[game_id][seat]


game_manager = GameManager()


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
    engine = get_engine_or_404(game_manager, game_id)
    return build_game_status_payload(engine, game_id)


@app.get("/api/game/{game_id}/players")
async def get_players(game_id: str):
    """Get players list"""
    engine = get_engine_or_404(game_manager, game_id)
    return [p.to_public_dict() for p in engine.players.values()]


@app.get("/api/game/{game_id}/player/{seat}")
async def get_player_view(game_id: str, seat: int):
    """Get player's private view"""
    engine = get_engine_or_404(game_manager, game_id)
    player = get_player_or_404(engine, seat)
    return player.to_private_dict()


@app.get("/api/game/{game_id}/log")
async def get_game_log(game_id: str, offset: int = 0, limit: int = 100):
    """Get game logs"""
    engine = get_engine_or_404(game_manager, game_id)
    return build_public_logs_payload(engine, offset, limit)


@app.post("/api/game/{game_id}/start")
async def start_game(game_id: str):
    """Start the game"""
    engine = get_engine_or_404(game_manager, game_id)
    # Start game in background
    asyncio.create_task(engine.start())
    return build_success_response("Game started")


@app.post("/api/game/{game_id}/pause")
async def pause_game(game_id: str):
    """Pause the game"""
    engine = get_engine_or_404(game_manager, game_id)
    engine.pause()
    return build_success_response("Game paused")


@app.post("/api/game/{game_id}/resume")
async def resume_game(game_id: str):
    """Resume the game"""
    engine = get_engine_or_404(game_manager, game_id)
    engine.resume()
    return build_success_response("对局已继续")


@app.post("/api/game/{game_id}/action")
async def submit_action(game_id: str, request: ActionRequest):
    """Submit human player action (REST fallback)"""
    engine = get_engine_or_404(game_manager, game_id)
    return submit_waiting_human_action(engine, request.data)


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
