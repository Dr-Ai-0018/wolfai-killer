"""
对局查询与上帝视角只读辅助逻辑。
"""

from typing import Any, Dict, List

from fastapi import HTTPException


def get_engine_or_404(game_manager: Any, game_id: str) -> Any:
    """获取对局实例，不存在则抛 404。"""
    engine = game_manager.get_game(game_id)
    if not engine:
        raise HTTPException(status_code=404, detail="未找到该对局")
    return engine


def get_player_or_404(engine: Any, seat: int) -> Any:
    """获取指定座位玩家，不存在则抛 404。"""
    player = engine.players.get(seat)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


def verify_god_mode_access(engine: Any, password: str) -> None:
    """校验上帝模式是否启用以及密码是否正确。"""
    if not engine.god_mode_password:
        raise HTTPException(status_code=403, detail="本局游戏未启用上帝模式")
    if password != engine.god_mode_password:
        raise HTTPException(status_code=403, detail="密码错误")


def build_game_status_payload(engine: Any, game_id: str) -> Dict[str, Any]:
    """构建对局状态响应。"""
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


def build_public_logs_payload(engine: Any, offset: int, limit: int) -> Dict[str, Any]:
    """构建公开日志响应。"""
    public_logs = [log for log in engine.logs if log.get("is_public", True)]
    return {"logs": public_logs[offset:offset + limit], "total": len(public_logs)}


def build_phantom_actions_payload(engine: Any) -> Dict[str, Any]:
    """构建冥界复盘响应。"""
    if engine.phase.value != "ended":
        return {"available": False, "message": "冥界复盘仅在游戏结束后可用", "phantom_actions": []}
    return {
        "available": True,
        "phantom_actions": engine.phantom_actions,
        "total": len(engine.phantom_actions),
    }
