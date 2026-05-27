"""
夜晚阶段流程编排辅助。
"""

from __future__ import annotations

import asyncio
from typing import Any


async def prepare_night_phase(engine: Any) -> None:
    engine.night_count += 1
    engine.phase = engine.phase.NIGHT if hasattr(engine.phase, "NIGHT") else engine.phase
    engine.night_kill_target = None
    engine.night_healed = False
    engine.night_poisoned = None
    engine.add_log("phase", f"第{engine.night_count}夜：天黑请闭眼")
    await engine.emit_state()
    await asyncio.sleep(1.5)


async def run_night_role_sequence(engine: Any) -> None:
    if engine.night_count == 1:
        await engine.announce_role_action("野孩子", "野孩子请睁眼，请选择一名玩家作为你的榜样")
        await engine.wild_child_action()
        await engine.announce_role_action("野孩子", "野孩子请闭眼", 1.5)

    if engine.night_count == 1 and not engine.cupid_paired:
        await engine.announce_role_action("丘比特", "丘比特请睁眼，请选择两名玩家成为情侣")
        await engine.cupid_action()
        await engine.announce_role_action("丘比特", "丘比特请闭眼", 1.5)

    if not engine.powers_disabled:
        await engine.announce_role_action("守卫", "守卫请睁眼，请选择你要守护的人")
        await engine.guard_action_with_phantom()
        await engine.announce_role_action("守卫", "守卫请闭眼", 1.5)

    await engine.announce_role_action("狼人", "狼人请睁眼，请讨论并选择你们的猎杀目标")
    await engine.wolf_action()
    await engine.announce_role_action("狼人", "狼人请闭眼", 1.5)

    if not engine.powers_disabled:
        await engine.announce_role_action("狐狸", "狐狸请睁眼，请选择一名玩家进行邻座嗅探")
        await engine.fox_action_with_phantom()
        await engine.announce_role_action("狐狸", "狐狸请闭眼", 1.5)

    if not engine.powers_disabled:
        await engine.announce_role_action("预言家", "预言家请睁眼，请选择你要查验的人")
        await engine.seer_action_with_phantom()
        await engine.announce_role_action("预言家", "预言家请闭眼", 1.5)

    if not engine.powers_disabled:
        await engine.announce_role_action("女巫", "女巫请睁眼")
        await engine.witch_action_with_phantom()
        await engine.announce_role_action("女巫", "女巫请闭眼", 1.5)

    await engine.clear_role_announcement()


async def execute_night_phase(engine: Any) -> None:
    await prepare_night_phase(engine)
    await run_night_role_sequence(engine)
    await engine.resolve_night()
