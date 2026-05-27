"""
对局主循环流程辅助。
"""

from __future__ import annotations

import asyncio
from typing import Any


async def emit_initial_roles(engine: Any) -> None:
    for seat, player in engine.players.items():
        await engine.emit("your_role", player.to_private_dict(), to_seat=seat)


async def wait_if_paused(engine: Any) -> None:
    while engine.paused:
        await asyncio.sleep(1)


async def run_game_round(engine: Any) -> bool:
    await wait_if_paused(engine)
    await engine.run_night()

    winner = engine.check_winner()
    if winner:
        await engine.end_game(winner)
        return True

    await wait_if_paused(engine)
    await engine.run_day()

    winner = engine.check_winner()
    if winner:
        await engine.end_game(winner)
        return True

    return False
