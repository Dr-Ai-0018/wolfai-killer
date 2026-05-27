"""
对局控制接口辅助逻辑。
"""

from typing import Any, Dict


def build_success_response(message: str) -> Dict[str, Any]:
    """构建统一成功响应。"""
    return {"success": True, "message": message}


def submit_waiting_human_action(engine: Any, action_data: Any) -> Dict[str, Any]:
    """提交等待中的真人操作，供 REST fallback 使用。"""
    if engine.waiting_for_human:
        success = engine.submit_human_action(engine.waiting_for_human, action_data)
        return {"success": success}
    return {"success": False, "message": "当前没有待提交的玩家操作"}
