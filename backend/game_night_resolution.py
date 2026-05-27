"""
夜晚结算辅助逻辑。
"""

from typing import Any, Dict, List, Optional


def should_apply_wolf_kill(target: Optional[int], healed: bool, guarded: Optional[int]) -> bool:
    """判断狼刀是否应当进入实际淘汰结算。"""
    return bool(target) and not healed and guarded != target


def append_unique_deaths(deaths: List[int], eliminated: List[int]) -> None:
    """将淘汰链中的座位追加到夜晚死亡列表，避免重复。"""
    for seat in eliminated:
        if seat not in deaths:
            deaths.append(seat)


def build_night_announcement(day_count: int, deaths: List[int]) -> Dict[str, Any]:
    """构建天亮公告日志载荷。"""
    ordered_deaths = sorted(deaths)
    if ordered_deaths:
        death_str = "、".join(str(seat) for seat in ordered_deaths)
        return {
            "type": "death",
            "content": f"第{day_count}天：天亮了，昨晚{death_str}号死亡",
            "meta": {"deaths": ordered_deaths},
        }
    return {
        "type": "phase",
        "content": f"第{day_count}天：天亮了，昨晚是平安夜",
        "meta": None,
    }
