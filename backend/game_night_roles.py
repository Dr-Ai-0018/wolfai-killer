"""
夜间角色行动流程辅助。
"""

from __future__ import annotations

import random
from typing import Any, List, Optional

from game_catalog import Camp, Role
from game_night_actions import (
    build_fox_action_log,
    build_fox_lose_power_log,
    build_fox_phantom_summary,
    build_fox_result_payload,
    build_guard_action_log,
    build_guard_phantom_summary,
    build_seer_action_log,
    build_seer_phantom_summary,
    build_seer_result_payload,
    build_witch_heal_log,
    build_witch_phantom_summary,
    build_witch_poison_log,
    build_wolf_action_log,
    parse_human_target_response,
    parse_human_witch_heal_response,
)
from game_phantom import pick_random_candidate, run_phantom_role_action


async def run_guard_action(engine: Any) -> None:
    guard = engine.get_player_by_role_any(Role.GUARD)

    async def run_live_action():
        candidates = [s for s in engine.get_alive_seats() if s != guard.guard_last_target]
        if guard.is_human:
            response = await engine.wait_for_human(
                guard.seat,
                "guard",
                {"candidates": candidates, "message": "请选择今晚要守护的玩家（不能连续守护同一人）"},
            )
            target = parse_human_target_response(response, candidates)
        else:
            target = await engine.generate_ai_guard_action(guard, candidates)

        if target and target in candidates:
            engine.night_guarded = target
            guard.guard_last_target = target
            payload = build_guard_action_log(guard.seat, target)
            engine.add_log(payload["type"], payload["content"], seat=payload["seat"], is_public=False, meta=payload["meta"])

    async def run_dead_ai_phantom():
        candidates = [s for s in engine.get_alive_seats() if s != guard.guard_last_target]
        phantom_target = await engine.generate_ai_guard_action(guard, candidates)
        engine.add_phantom_action(
            "守卫",
            guard.seat,
            "guard",
            phantom_target,
            build_guard_phantom_summary(phantom_target),
            engine.night_count,
        )

    await run_phantom_role_action(guard, (3.0, 6.0), run_live_action, run_dead_ai_phantom)


async def run_wolf_action(engine: Any) -> None:
    wolves = engine.get_alive_wolves()
    if not wolves:
        return

    candidates = [s for s in engine.get_alive_seats() if engine.players[s].camp != Camp.WOLF]
    human_wolf = next((w for w in wolves if w.is_human), None)

    if human_wolf:
        response = await engine.wait_for_human(
            human_wolf.seat,
            "wolf",
            {
                "candidates": candidates,
                "teammates": [w.seat for w in wolves if w.seat != human_wolf.seat],
                "message": "请选择今晚要击杀的目标",
            },
        )
        target = parse_human_target_response(response, candidates)
    else:
        target = await engine.generate_ai_wolf_action(wolves, candidates)

    if target and target in candidates:
        engine.night_kill_target = target
        payload = build_wolf_action_log(target)
        engine.add_log(payload["type"], payload["content"], is_public=False, meta=payload["meta"])


async def run_fox_action(engine: Any) -> None:
    fox = engine.get_player_by_role_any(Role.FOX)

    async def run_live_action():
        if not fox.fox_power_active:
            return
        candidates = engine.get_alive_seats()
        if fox.is_human:
            response = await engine.wait_for_human(
                fox.seat,
                "fox",
                {
                    "candidates": candidates,
                    "known_results": fox.fox_checks,
                    "message": "请选择一名玩家；你会嗅探该玩家及其左右邻座中是否存在狼人",
                },
            )
            target = parse_human_target_response(response, candidates)
        else:
            target = random.choice(candidates) if candidates else None

        if target and target in candidates:
            checked = engine.get_neighbor_triplet(target)
            found_wolf = any(engine.players[seat].camp == Camp.WOLF for seat in checked)
            result = "有狼人" if found_wolf else "没有狼人"
            fox.fox_checks[target] = result
            payload = build_fox_action_log(fox.seat, target, checked, result)
            engine.add_log(payload["type"], payload["content"], seat=payload["seat"], is_public=False, meta=payload["meta"])
            await engine.emit("fox_result", build_fox_result_payload(target, checked, result), to_seat=fox.seat)
            if not found_wolf:
                fox.fox_power_active = False
                payload = build_fox_lose_power_log(fox.seat, target, checked)
                engine.add_log(payload["type"], payload["content"], seat=payload["seat"], is_public=False, meta=payload["meta"])

    async def run_dead_ai_phantom():
        if not fox.fox_power_active:
            return
        candidates = engine.get_alive_seats()
        phantom_target = pick_random_candidate(candidates)
        if phantom_target:
            engine.add_phantom_action("狐狸", fox.seat, "fox", phantom_target, build_fox_phantom_summary(phantom_target), engine.night_count)

    await run_phantom_role_action(fox, (3.0, 6.0), run_live_action, run_dead_ai_phantom)


async def run_seer_action(engine: Any) -> None:
    seer = engine.get_player_by_role_any(Role.SEER)

    async def run_live_action():
        candidates = [s for s in engine.get_alive_seats() if s != seer.seat and s not in seer.seer_results]
        if seer.is_human:
            response = await engine.wait_for_human(
                seer.seat,
                "seer",
                {"candidates": candidates, "known_results": seer.seer_results, "message": "请选择要查验的玩家"},
            )
            target = parse_human_target_response(response, candidates)
        else:
            target = await engine.generate_ai_seer_action(seer, candidates)

        if target and target in candidates:
            result = "狼人" if engine.players[target].camp == Camp.WOLF else "好人"
            seer.seer_results[target] = result
            payload = build_seer_action_log(seer.seat, target, result)
            engine.add_log(payload["type"], payload["content"], seat=payload["seat"], is_public=False, meta=payload["meta"])
            await engine.emit("seer_result", build_seer_result_payload(target, result), to_seat=seer.seat)

    async def run_dead_ai_phantom():
        candidates = [s for s in engine.get_alive_seats() if s != seer.seat and s not in seer.seer_results]
        phantom_target = await engine.generate_ai_seer_action(seer, candidates)
        if phantom_target and phantom_target in candidates:
            phantom_result = "狼人" if engine.players[phantom_target].camp == Camp.WOLF else "好人"
            engine.add_phantom_action(
                "预言家",
                seer.seat,
                "seer",
                phantom_target,
                build_seer_phantom_summary(phantom_target, phantom_result),
                engine.night_count,
            )

    await run_phantom_role_action(seer, (3.0, 6.0), run_live_action, run_dead_ai_phantom)


async def run_witch_action(engine: Any) -> None:
    witch = engine.get_player_by_role_any(Role.WITCH)

    async def run_live_action():
        candidates = [s for s in engine.get_alive_seats() if s != witch.seat]
        if witch.has_heal and engine.night_kill_target:
            if witch.is_human:
                response = await engine.wait_for_human(
                    witch.seat,
                    "witch_heal",
                    {"victim": engine.night_kill_target, "message": f"今晚{engine.night_kill_target}号被刀，是否使用解药？"},
                )
                use_heal = parse_human_witch_heal_response(response)
            else:
                use_heal = await engine.generate_ai_witch_heal(witch, engine.night_kill_target)

            if use_heal:
                witch.has_heal = False
                engine.night_healed = True
                payload = build_witch_heal_log(witch.seat, engine.night_kill_target)
                engine.add_log(payload["type"], payload["content"], seat=payload["seat"], is_public=False, meta=payload["meta"])

        if witch.has_poison:
            if witch.is_human:
                response = await engine.wait_for_human(
                    witch.seat,
                    "witch_poison",
                    {"candidates": candidates, "message": "是否使用毒药？选择目标或跳过"},
                )
                target = parse_human_target_response(response, candidates)
            else:
                target = await engine.generate_ai_witch_poison(witch, candidates)

            if target and target in candidates:
                witch.has_poison = False
                engine.night_poisoned = target
                payload = build_witch_poison_log(witch.seat, target)
                engine.add_log(payload["type"], payload["content"], seat=payload["seat"], is_public=False, meta=payload["meta"])

    async def run_dead_ai_phantom():
        candidates = [s for s in engine.get_alive_seats() if s != witch.seat]
        phantom_heal = await engine.generate_ai_witch_heal(witch, engine.night_kill_target) if engine.night_kill_target else False
        phantom_poison = await engine.generate_ai_witch_poison(witch, candidates)
        engine.add_phantom_action(
            "女巫",
            witch.seat,
            "witch",
            phantom_poison,
            build_witch_phantom_summary(engine.night_kill_target, phantom_heal, phantom_poison),
            engine.night_count,
        )

    await run_phantom_role_action(witch, (4.0, 8.0), run_live_action, run_dead_ai_phantom)
