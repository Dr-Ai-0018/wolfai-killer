"""
app.py 普通对局只读接口辅助。
"""

from typing import Any, Dict

from game_views import (
    build_game_status_payload,
    build_public_logs_payload,
    get_engine_or_404,
    get_player_or_404,
)


def get_game_status_response(game_manager: Any, game_id: str) -> Dict[str, Any]:
    """构建对局状态接口响应。"""
    engine = get_engine_or_404(game_manager, game_id)
    return build_game_status_payload(engine, game_id)


def get_game_players_response(game_manager: Any, game_id: str) -> list[Dict[str, Any]]:
    """构建公开玩家列表响应。"""
    engine = get_engine_or_404(game_manager, game_id)
    return [player.to_public_dict() for player in engine.players.values()]


def get_game_player_view_response(game_manager: Any, game_id: str, seat: int) -> Dict[str, Any]:
    """构建指定座位玩家私有视角响应。"""
    engine = get_engine_or_404(game_manager, game_id)
    player = get_player_or_404(engine, seat)
    return player.to_private_dict()


def get_game_log_response(game_manager: Any, game_id: str, offset: int, limit: int) -> Dict[str, Any]:
    """构建公开日志响应。"""
    engine = get_engine_or_404(game_manager, game_id)
    return build_public_logs_payload(engine, offset, limit)
