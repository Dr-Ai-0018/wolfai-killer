"""
app.py 创建对局路由辅助。
"""

from typing import Any, Dict, List, Optional


def resolve_god_mode_password(god_mode: Any) -> Optional[str]:
    """从上帝模式配置中提取有效密码。"""
    if god_mode and getattr(god_mode, "enabled", False):
        return getattr(god_mode, "password", None)
    return None


def build_game_setup_kwargs(request: Any, avatars: List[str]) -> Dict[str, Any]:
    """构建 engine.setup 所需参数。"""
    return {
        "human_seats": request.human_seats,
        "total_players": request.total_players,
        "num_wolves": request.num_wolves,
        "role_config": request.role_config,
        "avatars": avatars,
        "random_models": request.random_models,
        "seat_model_map": request.seat_model_map,
    }


def build_create_game_response(engine: Any) -> Dict[str, Any]:
    """构建创建对局成功响应。"""
    return {
        "game_id": engine.game_id,
        "players": [player.to_public_dict() for player in engine.players.values()],
        "status": engine.phase.value,
        "god_mode_enabled": engine.god_mode_password is not None,
    }
