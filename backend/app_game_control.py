"""
app.py 普通对局控制接口辅助。
"""

from typing import Any, Dict

from game_control import build_success_response, submit_waiting_human_action
from game_views import get_engine_or_404


async def start_game_response(game_manager: Any, game_id: str, create_task_fn: Any) -> Dict[str, Any]:
    """启动对局并返回统一响应。"""
    engine = get_engine_or_404(game_manager, game_id)
    create_task_fn(engine.start())
    return build_success_response("Game started")


def pause_game_response(game_manager: Any, game_id: str) -> Dict[str, Any]:
    """暂停对局并返回统一响应。"""
    engine = get_engine_or_404(game_manager, game_id)
    engine.pause()
    return build_success_response("Game paused")


def resume_game_response(game_manager: Any, game_id: str) -> Dict[str, Any]:
    """继续对局并返回统一响应。"""
    engine = get_engine_or_404(game_manager, game_id)
    engine.resume()
    return build_success_response("对局已继续")


def submit_action_response(game_manager: Any, game_id: str, action_data: Any) -> Dict[str, Any]:
    """提交真人操作并返回统一响应。"""
    engine = get_engine_or_404(game_manager, game_id)
    return submit_waiting_human_action(engine, action_data)
