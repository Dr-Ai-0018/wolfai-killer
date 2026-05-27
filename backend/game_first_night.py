"""
首夜特殊角色行动流程辅助。
"""

from __future__ import annotations

import asyncio
import random
from typing import Any, List, Optional

from game_catalog import Role
from game_special_roles import (
    apply_cupid_pair,
    apply_wild_child_idol,
    build_cupid_action_log,
    build_cupid_phantom_decision,
    build_lover_info_payload,
    build_wild_child_action_log,
    build_wild_child_info_payload,
    build_wild_child_phantom_decision,
    choose_cupid_pair,
    choose_wild_child_idol,
    parse_cupid_pair_response,
    parse_wild_child_target_response,
)


async def run_cupid_action(engine: Any) -> None:
    cupid = engine.get_player_by_role_any(Role.CUPID)
    if not cupid:
        await asyncio.sleep(random.uniform(2.0, 4.0))
        return

    candidates = engine.get_alive_seats()
    requested_pair: Optional[List[int]] = None

    if cupid.alive:
        if cupid.is_human:
            response = await engine.wait_for_human(
                cupid.seat,
                "cupid",
                {
                    "candidates": candidates,
                    "message": "请选择两名玩家成为情侣",
                },
            )
            requested_pair = parse_cupid_pair_response(response, candidates)
        else:
            requested_pair = choose_cupid_pair(candidates)
    else:
        if not cupid.is_human:
            pair = choose_cupid_pair(candidates)
            engine.add_phantom_action("丘比特", cupid.seat, "cupid", None, build_cupid_phantom_decision(pair), engine.night_count)
        else:
            await asyncio.sleep(random.uniform(2.0, 4.0))
        return

    pair = choose_cupid_pair(candidates, requested_pair)
    if apply_cupid_pair(engine.players, pair):
        engine.cupid_paired = True
        payload = build_cupid_action_log(cupid.seat, pair)
        engine.add_log(payload["type"], payload["content"], seat=payload["seat"], is_public=False, meta=payload["meta"])
        for seat in pair:
            await engine.emit("lover_info", build_lover_info_payload(engine.players[seat].lover), to_seat=seat)


async def run_wild_child_action(engine: Any) -> None:
    wild_child = engine.get_player_by_role_any(Role.WILD_CHILD)
    if not wild_child or wild_child.idol is not None:
        await asyncio.sleep(random.uniform(2.0, 4.0))
        return

    candidates = [seat for seat in engine.get_alive_seats() if seat != wild_child.seat]
    requested_idol: Optional[int] = None

    if wild_child.alive:
        if wild_child.is_human:
            response = await engine.wait_for_human(
                wild_child.seat,
                "wild_child",
                {
                    "candidates": candidates,
                    "message": "请选择一名玩家作为你的榜样；若他死亡，你将转入狼人阵营",
                },
            )
            requested_idol = parse_wild_child_target_response(response, candidates)
        else:
            requested_idol = choose_wild_child_idol(candidates)
    else:
        if not wild_child.is_human:
            idol = choose_wild_child_idol(candidates)
            engine.add_phantom_action(
                "野孩子",
                wild_child.seat,
                "wild_child",
                idol,
                build_wild_child_phantom_decision(idol),
                engine.night_count,
            )
        else:
            await asyncio.sleep(random.uniform(2.0, 4.0))
        return

    idol = choose_wild_child_idol(candidates, requested_idol)
    if apply_wild_child_idol(wild_child, idol):
        payload = build_wild_child_action_log(wild_child.seat, idol)
        engine.add_log(payload["type"], payload["content"], seat=payload["seat"], is_public=False, meta=payload["meta"])
        await engine.emit("wild_child_info", build_wild_child_info_payload(idol), to_seat=wild_child.seat)
