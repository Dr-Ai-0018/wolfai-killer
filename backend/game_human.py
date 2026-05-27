"""
真人玩家行动等待与提交流程辅助。
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict


async def wait_for_human_action(
    engine: Any,
    seat: int,
    action_type: str,
    options: Dict[str, Any],
    timeout: int = 120,
) -> Any:
    engine.waiting_for_human = seat
    engine.human_action_type = action_type
    engine.human_action_options = options
    engine.human_response = None
    engine.human_response_event.clear()

    await engine.emit_state()
    await engine.emit(
        "action_required",
        {
            "seat": seat,
            "action_type": action_type,
            "options": options,
            "timeout": timeout,
        },
        to_seat=seat,
    )

    try:
        await asyncio.wait_for(engine.human_response_event.wait(), timeout=timeout)
        response = engine.human_response
    except asyncio.TimeoutError:
        response = None
        engine.add_log("system", f"{seat}号玩家超时，自动跳过", seat=seat)

    engine.waiting_for_human = None
    engine.human_action_type = None
    engine.human_action_options = {}
    await engine.emit_state()
    return response


def submit_human_action_response(engine: Any, seat: int, action_data: Any) -> bool:
    if engine.waiting_for_human != seat:
        return False
    engine.human_response = action_data
    engine.human_response_event.set()
    return True
