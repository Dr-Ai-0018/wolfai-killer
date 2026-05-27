"""
应用层配置与连接管理辅助。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import yaml
from fastapi import WebSocket

from game_engine import GameEngine


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


def load_game_manager_config(base_dir: str) -> Dict[str, Any]:
    """Load config.yaml and merge supported environment overrides."""
    config_path = os.path.join(base_dir, "config.yaml")
    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle)
    except Exception as error:
        print(f"加载配置失败：{error}")
        config = {}

    if "api" not in config:
        config["api"] = {}

    api_key = os.getenv("WEREWOLF_API_KEY")
    if api_key:
        config["api"]["api_key"] = api_key

    base_url = os.getenv("WEREWOLF_API_BASE_URL")
    if base_url:
        config["api"]["base_url"] = base_url

    default_timeout = os.getenv("WEREWOLF_API_DEFAULT_TIMEOUT")
    if default_timeout:
        try:
            config["api"]["default_timeout"] = int(default_timeout)
        except ValueError:
            pass

    model_timeout_overrides = parse_model_timeout_overrides(os.getenv("WEREWOLF_API_MODEL_TIMEOUTS"))
    if model_timeout_overrides:
        existing = config["api"].get("model_timeout_map", {})
        if not isinstance(existing, dict):
            existing = {}
        config["api"]["model_timeout_map"] = {**existing, **model_timeout_overrides}

    config["models"] = normalize_model_ids(config.get("models", []))
    return config


def list_avatar_files(base_dir: str) -> List[str]:
    """Get available emoji avatar filenames under backend/Emojis."""
    emojis_dir = os.path.join(base_dir, "Emojis")
    if not os.path.exists(emojis_dir):
        return []
    return [name for name in os.listdir(emojis_dir) if name.endswith(".webp")]


class GameManager:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.games: Dict[str, GameEngine] = {}
        self.connections: Dict[str, Dict[int, WebSocket]] = {}
        self.config: Dict[str, Any] = {}

    def load_config(self):
        self.config = load_game_manager_config(self.base_dir)

    def get_avatars(self) -> List[str]:
        return list_avatar_files(self.base_dir)

    def create_game(
        self,
        human_seats: List[int],
        total_players: int = 12,
        num_wolves: int = 3,
        role_config: Dict[str, int] | None = None,
        god_mode_password: Optional[str] = None,
    ) -> GameEngine:
        from datetime import datetime
        import uuid

        game_id = f"game_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        engine = GameEngine(game_id, self.config, god_mode_password=god_mode_password)

        async def broadcast(event: str, data: Dict[str, Any], to_seat: Optional[int] = None):
            await self.broadcast_to_game(game_id, event, data, to_seat)

        engine.set_broadcast(broadcast)
        self.games[game_id] = engine
        self.connections[game_id] = {}
        return engine

    async def broadcast_to_game(self, game_id: str, event: str, data: Dict[str, Any], to_seat: Optional[int] = None):
        if game_id not in self.connections:
            return

        message = json.dumps({"event": event, "data": data})
        if to_seat is not None:
            ws = self.connections[game_id].get(to_seat)
            if ws:
                try:
                    await ws.send_text(message)
                except Exception:
                    pass
            return

        for ws in self.connections[game_id].values():
            try:
                await ws.send_text(message)
            except Exception:
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
