"""
WebSocket 连接初始化与消息处理辅助逻辑。
"""

from typing import Any, Dict, Optional


def build_connected_payload(engine: Any, seat: int, player: Any) -> Dict[str, Any]:
    """构建 websocket 连接成功后的初始化载荷。"""
    return {
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
            },
        },
    }


def build_missing_game_payload() -> Dict[str, Any]:
    """构建对局不存在时的错误消息。"""
    return {"event": "error", "data": {"message": "未找到该对局"}}


def handle_websocket_message(engine: Any, seat: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """处理单条 websocket 消息，必要时返回响应消息。"""
    message_type = data.get("type")
    if message_type == "action":
        action_data = data.get("data", {})
        if engine.waiting_for_human == seat:
            success = engine.submit_human_action(seat, action_data)
            return {"event": "action_received", "data": {"success": success}}
        return None

    if message_type == "ping":
        return {"event": "pong", "data": {}}

    return None
