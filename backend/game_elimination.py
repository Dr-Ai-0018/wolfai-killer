"""
玩家淘汰链流程辅助。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from game_catalog import Camp, Role
from game_resolution import find_lover_chain_target, resolve_immediate_elimination_rule


async def resolve_immediate_elimination(engine: Any, seat: int, cause: str) -> Optional[List[int]]:
    player = engine.players[seat]
    immediate_effect = resolve_immediate_elimination_rule(player, cause, engine.day_count)
    if not immediate_effect:
        return None

    if immediate_effect.kind == "angel_victory":
        engine.angel_victory_seat = seat
        engine.add_log(
            "angel_victory",
            f"{seat}号天使在开局阶段达成了自己的死亡胜利条件。",
            seat=seat,
            meta={"seat": seat, "role": player.role.value, "cause": cause, "winner": "天使阵营"},
        )
        return [seat]

    if immediate_effect.kind == "elder_survive":
        engine.add_log(
            "system",
            f"{seat}号长老承受了第一次狼人袭击，侥幸存活。",
            meta={"seat": seat, "role": player.role.value, "cause": cause, "elder_lives": player.elder_lives},
        )
        return []

    if immediate_effect.kind == "blessed_survive":
        engine.add_log(
            "system",
            f"{seat}号受祝福者抵挡了第一次狼人袭击，侥幸存活。",
            meta={"seat": seat, "role": player.role.value, "cause": cause, "blessing_used": True},
        )
        return []

    if immediate_effect.kind == "cursed_turn":
        engine.add_log(
            "system",
            f"{seat}号被狼人诅咒后未死亡，已秘密转入狼人阵营。",
            seat=seat,
            is_public=False,
            meta={"seat": seat, "role": player.role.value, "cause": cause, "action": "turn_wolf"},
        )
        await engine.emit("cursed_turned", {"camp": Camp.WOLF.value}, to_seat=seat)
        return []

    if immediate_effect.kind == "idiot_reveal":
        engine.add_log(
            "reveal",
            f"{seat}号被票出时翻牌为白痴，免于出局，但此后失去投票权。",
            meta={"seat": seat, "role": player.role.value, "cause": cause, "can_vote": False},
        )
        return []

    return None


def apply_primary_elimination(engine: Any, seat: int, cause: str) -> List[int]:
    player = engine.players[seat]
    player.alive = False
    eliminated = [seat]

    if player.role == Role.ELDER and engine.should_disable_powers_for_elder(cause):
        engine.disable_good_powers()

    lover_seat = find_lover_chain_target(engine.players, seat)
    if lover_seat:
        lover = engine.players[lover_seat]
        lover.alive = False
        eliminated.append(lover_seat)
        engine.add_log(
            "system",
            f"{lover_seat}号因情侣殉情而死亡。",
            meta={"seat": lover_seat, "cause": "lover_suicide", "lover_of": seat},
        )
        if lover.role == Role.ELDER and engine.should_disable_powers_for_elder("lover_suicide"):
            engine.disable_good_powers()

    return eliminated


async def resolve_post_elimination_effects(engine: Any, eliminated: List[int]) -> None:
    awakened_children: List[int] = []
    for eliminated_seat in list(eliminated):
        awakened_children.extend(await engine.awaken_wild_children_for_idol(eliminated_seat))
    if awakened_children:
        engine.add_log(
            "system",
            "有野孩子在榜样死亡后秘密转化为狼人。",
            is_public=False,
            meta={"awakened": awakened_children, "eliminated": list(eliminated)},
        )


async def resolve_super_saint_revenge(
    engine: Any,
    player: Any,
    seat: int,
    cause: str,
    allow_hunter: bool,
    context: Dict[str, Any],
    eliminated: List[int],
) -> None:
    if cause != "vote" or player.role != Role.SUPER_SAINT:
        return

    last_voter = context.get("last_voter")
    if not isinstance(last_voter, int):
        return

    target = engine.players.get(last_voter)
    if not target or not target.alive:
        return

    eliminated.extend(
        await engine.eliminate_player(
            last_voter,
            "super_saint",
            allow_hunter=allow_hunter,
            context={"triggered_by": seat},
        )
    )
    engine.add_log(
        "super_saint",
        f"{seat}号圣徒被公投出局后发动反噬，带走了最后投票的{last_voter}号。",
        seat=seat,
        meta={"seat": seat, "target": last_voter, "cause": "vote"},
    )


async def resolve_hunter_chain(engine: Any, eliminated: List[int], allow_hunter: bool) -> None:
    if not allow_hunter:
        return

    for eliminated_seat in list(eliminated):
        eliminated_player = engine.players[eliminated_seat]
        if eliminated_player.role == Role.HUNTER and not engine.powers_disabled:
            await engine.hunter_action(eliminated_seat)
