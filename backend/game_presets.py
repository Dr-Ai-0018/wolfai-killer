"""
官方风格预设板子定义与解析。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


GAME_PRESETS: List[Dict[str, Any]] = [
    {
        "id": "standard_6p",
        "name": "标准六人局",
        "description": "2狼 + 预言家 + 女巫 + 守卫 + 村民，适合快速验证核心昼夜流程。",
        "total_players": 6,
        "num_wolves": 2,
        "role_config": {"WOLF": 2, "SEER": 1, "WITCH": 1, "GUARD": 1, "VILLAGER": 1},
    },
    {
        "id": "lovers_7p",
        "name": "情侣七人局",
        "description": "在核心板子中加入丘比特，用于验证情侣链和第三方压力。",
        "total_players": 7,
        "num_wolves": 2,
        "role_config": {"WOLF": 2, "CUPID": 1, "SEER": 1, "WITCH": 1, "GUARD": 1, "VILLAGER": 1},
    },
    {
        "id": "advanced_8p",
        "name": "进阶八人局",
        "description": "加入白痴、长老、替罪羊与狐狸中的低耦合扩展角色，用于评估信息与投票平衡。",
        "total_players": 8,
        "num_wolves": 2,
        "role_config": {"WOLF": 2, "SEER": 1, "WITCH": 1, "IDIOT": 1, "ELDER": 1, "FOX": 1, "VILLAGER": 1},
    },
]


def build_game_preset_catalog() -> List[Dict[str, Any]]:
    return [dict(preset) for preset in GAME_PRESETS]


def get_game_preset(preset_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not preset_id:
        return None
    for preset in GAME_PRESETS:
        if preset["id"] == preset_id:
            return dict(preset)
    return None


def apply_game_preset_to_request(request: Any, preset: Optional[Dict[str, Any]]) -> Any:
    if not preset:
        return request

    request.total_players = int(preset["total_players"])
    request.num_wolves = int(preset["num_wolves"])
    request.role_config = dict(preset["role_config"])
    return request
