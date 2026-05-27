"""
夜间真实行动与死亡虚拟行动辅助逻辑。
"""

import asyncio
import random
from typing import Any, Awaitable, Callable, Optional, Sequence, Tuple


async def sleep_for_missing_role(delay_range: Tuple[float, float]) -> None:
    """在角色不存在时模拟等待时长。"""
    await asyncio.sleep(random.uniform(*delay_range))


async def sleep_for_dead_human(delay_range: Tuple[float, float]) -> None:
    """在人类玩家死亡时模拟等待时长。"""
    await asyncio.sleep(random.uniform(*delay_range))


async def run_phantom_role_action(
    role_player: Any,
    delay_range: Tuple[float, float],
    run_live_action: Callable[[], Awaitable[None]],
    run_dead_ai_phantom: Callable[[], Awaitable[None]],
) -> bool:
    """
    统一处理夜间角色的真实行动/死亡虚拟行动分支。

    返回值表示是否存在该角色。
    """
    if not role_player:
        await sleep_for_missing_role(delay_range)
        return False

    if role_player.alive:
        await run_live_action()
        return True

    if role_player.is_human:
        await sleep_for_dead_human(delay_range)
        return True

    await run_dead_ai_phantom()
    return True


def pick_random_candidate(candidates: Sequence[int]) -> Optional[int]:
    """从候选列表中随机选取一个目标。"""
    return random.choice(list(candidates)) if candidates else None
