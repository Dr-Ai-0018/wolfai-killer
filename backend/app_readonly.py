"""
app.py 只读配置与统计响应辅助。
"""

from typing import Any, Callable, Dict, Iterable, List

from fastapi import HTTPException


def build_model_catalog(raw_models: Any, normalize_model_ids: Callable[[Any], List[str]]) -> List[Dict[str, str]]:
    """将模型配置转换为前端可消费的列表结构。"""
    return [{"id": model_id, "label": model_id} for model_id in normalize_model_ids(raw_models)]


def count_active_games(games: Iterable[Any]) -> int:
    """统计当前处于进行中的对局数量。"""
    return len([game for game in games if game.phase.value not in ["ended", "waiting"]])


def build_stats_overview_payload(overview: Dict[str, Any], games: Iterable[Any]) -> Dict[str, Any]:
    """构建包含活跃对局数的统计总览响应。"""
    payload = dict(overview)
    payload["active_games"] = count_active_games(games)
    return payload


def get_stats_game_detail_or_404(stats_manager: Any, game_id: str) -> Dict[str, Any]:
    """获取单局详情，不存在时抛 404。"""
    game = stats_manager.get_game_detail(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="未找到该对局")
    return game


def build_admin_config_payload(game_config: Dict[str, Any], normalize_model_ids: Callable[[Any], List[str]]) -> Dict[str, Any]:
    """构建管理员只读配置响应。"""
    api_config = game_config.get("api", {})
    model_ids = normalize_model_ids(game_config.get("models", []))
    return {
        "api_url": api_config.get("base_url", ""),
        "api_key_masked": "***" + api_config.get("api_key", "")[-4:] if api_config.get("api_key") else "",
        "models": model_ids,
        "model_ids": model_ids,
        "default_timeout": api_config.get("default_timeout", 60),
        "model_timeout_map": api_config.get("model_timeout_map", {}),
    }
