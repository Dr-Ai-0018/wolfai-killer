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
