"""
首夜特殊角色辅助逻辑。
"""

import random
from typing import Any, Dict, List, Optional


def choose_cupid_pair(
    candidates: List[int],
    requested_pair: Optional[List[int]] = None,
) -> List[int]:
    """规范化丘比特配对结果，不合法时回退到随机有效配对。"""
    pair = list(requested_pair or [])
    if len(pair) == 2 and pair[0] != pair[1] and all(seat in candidates for seat in pair):
        return pair

    available = list(candidates)
    return random.sample(available, 2) if len(available) >= 2 else []


def choose_wild_child_idol(
    candidates: List[int],
    requested_target: Optional[int] = None,
) -> Optional[int]:
    """规范化野孩子榜样选择，不合法时回退到随机有效目标。"""
    if requested_target in candidates:
        return requested_target
    return random.choice(candidates) if candidates else None


def parse_cupid_pair_response(response: Optional[Dict[str, Any]], candidates: List[int]) -> Optional[List[int]]:
    """解析真人丘比特提交的配对请求。"""
    raw_pair = response.get("pair") if response else None
    if not isinstance(raw_pair, list):
        return None

    parsed: List[int] = []
    for item in raw_pair:
        try:
            seat = int(item)
        except (TypeError, ValueError):
            continue
        if seat in candidates:
            parsed.append(seat)
    return parsed


def parse_wild_child_target_response(response: Optional[Dict[str, Any]], candidates: List[int]) -> Optional[int]:
    """解析真人野孩子提交的榜样目标。"""
    raw_target = response.get("target") if response else None
    if raw_target is None:
        return None
    try:
        parsed = int(raw_target)
    except (TypeError, ValueError):
        return None
    return parsed if parsed in candidates else None


def build_cupid_phantom_decision(pair: List[int]) -> str:
    """构建丘比特虚拟行动描述。"""
    return f"连接{pair[0]}号与{pair[1]}号" if len(pair) == 2 else "跳过"


def build_cupid_action_log(seat: int, pair: List[int]) -> Dict[str, Any]:
    """构建丘比特行动日志 payload。"""
    first, second = pair
    return {
        "type": "cupid_action",
        "content": f"[上帝视角] 丘比特连接了{first}号与{second}号",
        "seat": seat,
        "meta": {"actor_role": "丘比特", "pair": sorted(pair), "action": "pair"},
    }


def build_lover_info_payload(lover: Optional[int]) -> Dict[str, Any]:
    """构建情侣信息事件载荷。"""
    return {"lover": lover}


def build_wild_child_phantom_decision(idol: Optional[int]) -> str:
    """构建野孩子虚拟行动描述。"""
    return f"认{idol}号为榜样" if idol else "跳过"


def build_wild_child_action_log(seat: int, idol: int) -> Dict[str, Any]:
    """构建野孩子行动日志 payload。"""
    return {
        "type": "wild_child_action",
        "content": f"[上帝视角] {seat}号野孩子认定了{idol}号为榜样",
        "seat": seat,
        "meta": {"actor_role": "野孩子", "idol": idol, "action": "idol"},
    }


def build_wild_child_info_payload(idol: int) -> Dict[str, Any]:
    """构建野孩子榜样事件载荷。"""
    return {"idol": idol}


def apply_cupid_pair(players: Dict[int, Any], pair: List[int]) -> bool:
    """把情侣关系写回玩家状态。"""
    if len(pair) != 2 or pair[0] == pair[1]:
        return False

    first, second = pair
    if first not in players or second not in players:
        return False

    players[first].lover = second
    players[second].lover = first
    return True


def apply_wild_child_idol(player: Any, idol: Optional[int]) -> bool:
    """把野孩子榜样写回玩家状态。"""
    if idol is None:
        return False
    player.idol = idol
    return True
