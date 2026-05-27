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
from pydantic import BaseModel, ConfigDict
from dotenv import load_dotenv, set_key
import yaml
import httpx
import secrets

from admin_auth import create_admin_token, get_admin_password, verify_token
from admin_config import fetch_remote_model_ids, normalize_openai_v1_base_url, update_admin_config_state
from game_engine import GameEngine
from game_stats import stats_manager

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


def build_model_catalog(raw_models: Any) -> List[Dict[str, str]]:
    """Return frontend-friendly model entries from config or remote payloads."""
    return [{"id": model_id, "label": model_id} for model_id in normalize_model_ids(raw_models)]


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


# ========== Pydantic Models ==========

class GodModeConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    enabled: bool = False
    password: str = ""


class CreateGameRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    human_seats: List[int] = []
    total_players: int = 12
    num_wolves: int = 3
    role_config: Optional[Dict[str, int]] = None  # 自定义角色配置，如 {"WOLF": 3, "SEER": 1, "WITCH": 1}
    random_models: bool = True  # 是否随机分配模型
    seat_model_map: Optional[Dict[int, str]] = None  # 手动模型分配：座位号 -> 模型名
    god_mode: Optional[GodModeConfig] = None


def validate_role_balance(total_players: int, role_config: Optional[Dict[str, int]], num_wolves: int) -> None:
    wolf_role_codes = {"WOLF", "WOLF_KING", "WHITE_WOLF", "BEAUTY"}
    configured_wolves = num_wolves

    if role_config:
        configured_wolves = sum(int(role_config.get(code, 0) or 0) for code in wolf_role_codes)
        total_roles = sum(int(count or 0) for count in role_config.values())
        if total_roles != total_players:
            raise HTTPException(status_code=400, detail="角色数量必须与总人数一致")

    if configured_wolves < 1:
        raise HTTPException(status_code=400, detail="至少需要 1 个狼人阵营角色")

    max_wolves = max(1, (total_players - 1) // 3)
    if configured_wolves > max_wolves:
        raise HTTPException(
            status_code=400,
            detail=f"当前 {total_players} 人局最多允许 {max_wolves} 个狼人阵营角色，避免出现人数过快持平的失衡配置",
        )


class ActionRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    action_type: str
    data: Dict[str, Any] = {}


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
    return build_model_catalog(game_manager.config.get("models", []))


@app.get("/api/stats/overview")
async def get_stats():
    """获取总览统计"""
    overview = stats_manager.get_overview()
    # 添加当前活跃游戏数
    overview["active_games"] = len([g for g in game_manager.games.values() if g.phase.value not in ["ended", "waiting"]])
    return overview


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
    game = stats_manager.get_game_detail(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="未找到该对局")
    return game


@app.post("/api/game/create")
async def create_game(request: CreateGameRequest):
    """Create a new game"""
    validate_role_balance(request.total_players, request.role_config, request.num_wolves)

    # 处理上帝模式配置
    god_mode_password = None
    if request.god_mode and request.god_mode.enabled:
        god_mode_password = request.god_mode.password
    
    engine = game_manager.create_game(
        human_seats=request.human_seats,
        total_players=request.total_players,
        num_wolves=request.num_wolves,
        role_config=request.role_config,
        god_mode_password=god_mode_password
    )
    
    # Setup with avatars and model configuration
    avatars = game_manager.get_avatars()
    await engine.setup(
        human_seats=request.human_seats,
        total_players=request.total_players,
        num_wolves=request.num_wolves,
        role_config=request.role_config,
        avatars=avatars,
        random_models=request.random_models,
        seat_model_map=request.seat_model_map
    )
    
    return {
        "game_id": engine.game_id,
        "players": [p.to_public_dict() for p in engine.players.values()],
        "status": engine.phase.value,
        "god_mode_enabled": engine.god_mode_password is not None,
    }


@app.get("/api/game/{game_id}/status")
async def get_game_status(game_id: str):
    """Get game status"""
    engine = game_manager.get_game(game_id)
    if not engine:
        raise HTTPException(status_code=404, detail="未找到该对局")
    
    return {
        "game_id": game_id,
        "phase": engine.phase.value,
        "day_count": engine.day_count,
        "night_count": engine.night_count,
        "paused": engine.paused,
        "winner": engine.winner,
        "alive_seats": engine.get_alive_seats(),
        "waiting_for_human": engine.waiting_for_human,
        "human_action_type": engine.human_action_type,
        "human_action_options": engine.human_action_options,
        "day_summary": engine.build_day_summary(),
    }


@app.get("/api/game/{game_id}/players")
async def get_players(game_id: str):
    """Get players list"""
    engine = game_manager.get_game(game_id)
    if not engine:
        raise HTTPException(status_code=404, detail="未找到该对局")
    
    return [p.to_public_dict() for p in engine.players.values()]


@app.get("/api/game/{game_id}/player/{seat}")
async def get_player_view(game_id: str, seat: int):
    """Get player's private view"""
    engine = game_manager.get_game(game_id)
    if not engine:
        raise HTTPException(status_code=404, detail="未找到该对局")
    
    player = engine.players.get(seat)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    return player.to_private_dict()


@app.get("/api/game/{game_id}/log")
async def get_game_log(game_id: str, offset: int = 0, limit: int = 100):
    """Get game logs"""
    engine = game_manager.get_game(game_id)
    if not engine:
        raise HTTPException(status_code=404, detail="未找到该对局")
    
    public_logs = [log for log in engine.logs if log.get("is_public", True)]
    return {"logs": public_logs[offset:offset+limit], "total": len(public_logs)}


@app.post("/api/game/{game_id}/start")
async def start_game(game_id: str):
    """Start the game"""
    engine = game_manager.get_game(game_id)
    if not engine:
        raise HTTPException(status_code=404, detail="未找到该对局")
    
    # Start game in background
    asyncio.create_task(engine.start())
    
    return {"success": True, "message": "Game started"}


@app.post("/api/game/{game_id}/pause")
async def pause_game(game_id: str):
    """Pause the game"""
    engine = game_manager.get_game(game_id)
    if not engine:
        raise HTTPException(status_code=404, detail="未找到该对局")
    
    engine.pause()
    return {"success": True, "message": "Game paused"}


@app.post("/api/game/{game_id}/resume")
async def resume_game(game_id: str):
    """Resume the game"""
    engine = game_manager.get_game(game_id)
    if not engine:
        raise HTTPException(status_code=404, detail="未找到该对局")
    
    engine.resume()
    return {"success": True, "message": "对局已继续"}


@app.post("/api/game/{game_id}/action")
async def submit_action(game_id: str, request: ActionRequest):
    """Submit human player action (REST fallback)"""
    engine = game_manager.get_game(game_id)
    if not engine:
        raise HTTPException(status_code=404, detail="未找到该对局")
    
    if engine.waiting_for_human:
        success = engine.submit_human_action(engine.waiting_for_human, request.data)
        return {"success": success}
    
    return {"success": False, "message": "当前没有待提交的玩家操作"}


class GodModeVerifyRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    password: str


class AdminConfigUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    models: Optional[List[str]] = None
    model_ids: Optional[List[str]] = None


class FetchModelsRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    api_url: str
    api_key: str


class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    password: str


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
    admin_pwd = get_admin_password()
    return {
        "configured": bool(admin_pwd),
        "message": "管理员密码已配置" if admin_pwd else "请在.env中设置WEREWOLF_ADMIN_PASSWORD"
    }


@app.post("/api/admin/login")
async def admin_login(request: AdminLoginRequest):
    """Admin login - returns JWT token"""
    admin_pwd = get_admin_password()
    if not admin_pwd:
        raise HTTPException(status_code=503, detail="管理员密码未配置，请在.env中设置WEREWOLF_ADMIN_PASSWORD")
    
    if secrets.compare_digest(request.password, admin_pwd):
        token_data = create_admin_token()
        return {
            "success": True, 
            "message": "登录成功",
            **token_data
        }
    
    raise HTTPException(status_code=403, detail="密码错误")


@app.post("/api/admin/refresh")
async def refresh_admin_token(admin: dict = Depends(get_current_admin)):
    """Refresh JWT token"""
    token_data = create_admin_token()
    return {
        "success": True,
        "message": "登录凭证已刷新",
        **token_data
    }


@app.get("/api/admin/verify")
async def verify_admin_token(admin: dict = Depends(get_current_admin)):
    """Verify current token is valid"""
    return {
        "valid": True,
        "admin": admin.get("sub"),
        "expires_at": datetime.fromtimestamp(admin.get("exp", 0)).isoformat()
    }


@app.get("/api/admin/config")
async def get_admin_config(_: dict = Depends(get_current_admin)):
    """获取当前配置（脱敏）"""
    api_config = game_manager.config.get("api", {})
    model_ids = normalize_model_ids(game_manager.config.get("models", []))
    return {
        "api_url": api_config.get("base_url", ""),
        "api_key_masked": "***" + api_config.get("api_key", "")[-4:] if api_config.get("api_key") else "",
        "models": model_ids,
        "model_ids": model_ids,
        "default_timeout": api_config.get("default_timeout", 60),
        "model_timeout_map": api_config.get("model_timeout_map", {}),
    }


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
    
    return {"success": True, "message": "配置已更新"}


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
        return {
            "success": True,
            "models": model_ids,
            "model_ids": model_ids,
            "total": len(model_ids)
        }
    except ValueError as e:
        return {"success": False, "message": str(e)}
    except httpx.HTTPStatusError as e:
        return {"success": False, "message": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/game/{game_id}/god-mode/verify")
async def verify_god_mode(game_id: str, request: GodModeVerifyRequest):
    """验证上帝模式密码"""
    engine = game_manager.get_game(game_id)
    if not engine:
        raise HTTPException(status_code=404, detail="未找到该对局")
    
    if not engine.god_mode_password:
        return {"success": False, "message": "本局游戏未启用上帝模式"}
    
    if request.password == engine.god_mode_password:
        return {"success": True, "message": "验证成功"}
    
    return {"success": False, "message": "密码错误"}


@app.get("/api/game/{game_id}/god-mode/logs")
async def get_god_mode_logs(game_id: str, password: str, offset: int = 0, limit: int = 100):
    """获取上帝模式日志（包含所有私密信息）"""
    engine = game_manager.get_game(game_id)
    if not engine:
        raise HTTPException(status_code=404, detail="未找到该对局")
    
    if not engine.god_mode_password:
        raise HTTPException(status_code=403, detail="本局游戏未启用上帝模式")
    
    if password != engine.god_mode_password:
        raise HTTPException(status_code=403, detail="密码错误")
    
    # 返回所有日志（包括私密日志）
    return {"logs": engine.logs[offset:offset+limit], "total": len(engine.logs)}


@app.get("/api/game/{game_id}/god-mode/players")
async def get_god_mode_players(game_id: str, password: str):
    """获取所有玩家的完整信息（包括身份）"""
    engine = game_manager.get_game(game_id)
    if not engine:
        raise HTTPException(status_code=404, detail="未找到该对局")
    
    if not engine.god_mode_password:
        raise HTTPException(status_code=403, detail="本局游戏未启用上帝模式")
    
    if password != engine.god_mode_password:
        raise HTTPException(status_code=403, detail="密码错误")
    
    # 返回所有玩家的私密信息
    return [p.to_private_dict() for p in engine.players.values()]


@app.get("/api/game/{game_id}/phantom-actions")
async def get_phantom_actions(game_id: str):
    """获取冥界复盘数据 - 死亡角色的虚拟行动记录（仅游戏结束后可见）"""
    engine = game_manager.get_game(game_id)
    if not engine:
        raise HTTPException(status_code=404, detail="未找到该对局")
    
    # 只有游戏结束后才能查看冥界复盘
    if engine.phase.value != "ended":
        return {"available": False, "message": "冥界复盘仅在游戏结束后可用", "phantom_actions": []}
    
    return {
        "available": True,
        "phantom_actions": engine.phantom_actions,
        "total": len(engine.phantom_actions)
    }


# ========== WebSocket Endpoint ==========

@app.websocket("/ws/{game_id}/{seat}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, seat: int):
    """WebSocket connection for real-time game updates"""
    await websocket.accept()
    
    engine = game_manager.get_game(game_id)
    if not engine:
        await websocket.send_json({"event": "error", "data": {"message": "未找到该对局"}})
        await websocket.close()
        return
    
    # Register connection
    game_manager.add_connection(game_id, seat, websocket)
    
    # Send initial state
    player = engine.players.get(seat)
    if player:
        await websocket.send_json({
            "event": "connected",
            "data": {
                "seat": seat,
                "role": player.to_private_dict(),
                "game_state": {
                    "phase": engine.phase.value,
                    "day_count": engine.day_count,
                    "night_count": engine.night_count,
                    "players": [p.to_public_dict() for p in engine.players.values()],
                    "logs": [log for log in engine.logs if log.get("is_public", True)][-50:],
                    "waiting_for_human": engine.waiting_for_human,
                    "human_action_type": engine.human_action_type,
                    "human_action_options": engine.human_action_options,
                    "god_mode_enabled": engine.god_mode_password is not None,
                }
            }
        })
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_json()
            
            if data.get("type") == "action":
                # Human player action
                action_data = data.get("data", {})
                if engine.waiting_for_human == seat:
                    engine.submit_human_action(seat, action_data)
                    await websocket.send_json({
                        "event": "action_received",
                        "data": {"success": True}
                    })
            
            elif data.get("type") == "ping":
                await websocket.send_json({"event": "pong", "data": {}})
    
    except WebSocketDisconnect:
        game_manager.remove_connection(game_id, seat)
    except Exception as e:
        print(f"实时通道错误：{e}")
        game_manager.remove_connection(game_id, seat)


# ========== Main ==========

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
