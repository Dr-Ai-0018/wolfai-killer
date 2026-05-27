"""
白天投票阶段流程编排辅助。
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Tuple

from game_catalog import Role
from game_vote import (
    apply_vote_rights,
    build_cast_vote_log,
    build_human_vote_options,
    build_scapegoat_tie_log,
    build_skipped_vote_log,
    build_valid_vote_targets,
    build_vote_eliminate_log,
    build_vote_result_log,
    build_vote_tie_log,
    record_vote_choice,
    resolve_vote_round,
)


async def collect_vote_round(engine: Any) -> Tuple[Dict[int, int], Dict[int, int]]:
    candidates = engine.get_alive_seats()
    votes: Dict[int, int] = {}
    last_voter_by_target: Dict[int, int] = {}

    apply_vote_rights(
        engine.players,
        engine.get_alive_seats(),
        engine.restricted_voters_next_day,
    )
    if engine.restricted_voters_next_day is not None:
        engine.restricted_voters_next_day = None

    for seat in sorted(engine.get_alive_seats()):
        player = engine.players[seat]
        if not player.can_vote:
            payload = build_skipped_vote_log(seat)
            engine.add_log(payload["type"], payload["content"], seat=payload["seat"], meta=payload["meta"])
            await engine.emit_state()
            await asyncio.sleep(0.3)
            continue

        valid_targets = build_valid_vote_targets(candidates, seat)
        if player.is_human:
            response = await engine.wait_for_human(seat, "vote", build_human_vote_options(valid_targets, votes))
            target = response.get("target") if response else None
        else:
            target = await engine.generate_ai_vote(player, valid_targets, votes)

        if target and target in valid_targets:
            record_vote_choice(votes, last_voter_by_target, seat, target)
            payload = build_cast_vote_log(seat, target)
            engine.add_log(payload["type"], payload["content"], seat=payload["seat"], meta=payload["meta"])
            await engine.emit_state()
            await asyncio.sleep(0.3)

    return votes, last_voter_by_target


async def resolve_vote_outcome(engine: Any, votes: Dict[int, int], last_voter_by_target: Dict[int, int]) -> None:
    resolution = resolve_vote_round(votes)
    if not resolution:
        return

    if not resolution.is_tie:
        eliminated = resolution.eliminated_seat
        assert eliminated is not None
        eliminated_chain = await engine.eliminate_player(
            eliminated,
            "vote",
            context={"last_voter": last_voter_by_target.get(eliminated)},
        )
        if eliminated_chain:
            payload = build_vote_eliminate_log(resolution, eliminated_chain)
        else:
            payload = build_vote_result_log(resolution)
        engine.add_log(payload["type"], payload["content"], meta=payload["meta"])
        return

    scapegoat = engine.get_player_by_role(Role.SCAPEGOAT)
    if scapegoat:
        scapegoat_seat = scapegoat.seat
        eliminated_chain = await engine.eliminate_player(
            scapegoat_seat,
            "scapegoat",
            allow_hunter=False,
            context={"tie_targets": list(resolution.top_targets)},
        )
        await engine.scapegoat_choose_voters(scapegoat_seat)
        payload = build_scapegoat_tie_log(resolution, scapegoat_seat, eliminated_chain)
    else:
        payload = build_vote_tie_log(resolution)
    engine.add_log(payload["type"], payload["content"], meta=payload["meta"])
