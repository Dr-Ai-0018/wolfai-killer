#!/usr/bin/env python3
"""
Run isolated live-flow validation for extension-role scenarios until key evidence appears.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import backend.scripts.run_batch_reviews as batch


REPORT_ROOT = ROOT / "data" / "reports" / f"validate_extension_live_flow_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
REPORT_ROOT.mkdir(parents=True, exist_ok=True)
batch.SCENARIO_TIMEOUT_SECONDS = 180
FAST_MODEL = "gpt-5.4-mini"
FAST_DEFAULT_TIMEOUT = "15"
FAST_MODEL_TIMEOUTS = "gpt-5.4-mini=15,gpt-5.4=20,gpt-5.3-codex=20,gpt-5.2=20"


SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "7p-idiot-2wolf-seer-witch-vill2",
        "total_players": 7,
        "num_wolves": 2,
        "role_config": {"WOLF": 2, "IDIOT": 1, "SEER": 1, "WITCH": 1, "VILLAGER": 2},
        "max_runs": 8,
        "target_human_role": "白痴",
    },
    {
        "name": "7p-super-saint-2wolf-seer-witch-vill2",
        "total_players": 7,
        "num_wolves": 2,
        "role_config": {"WOLF": 2, "SUPER_SAINT": 1, "SEER": 1, "WITCH": 1, "VILLAGER": 2},
        "max_runs": 8,
        "target_human_role": "圣徒",
    },
    {
        "name": "7p-wildchild-2wolf-seer-witch-vill2",
        "total_players": 7,
        "num_wolves": 2,
        "role_config": {"WOLF": 2, "WILD_CHILD": 1, "SEER": 1, "WITCH": 1, "VILLAGER": 2},
        "max_runs": 8,
        "target_human_role": "野孩子",
    },
    {
        "name": "7p-cursed-2wolf-seer-witch-vill2",
        "total_players": 7,
        "num_wolves": 2,
        "role_config": {"WOLF": 2, "CURSED": 1, "SEER": 1, "WITCH": 1, "VILLAGER": 2},
        "max_runs": 8,
        "target_human_role": "被诅咒者",
    },
    {
        "name": "7p-blessed-2wolf-seer-witch-vill2",
        "total_players": 7,
        "num_wolves": 2,
        "role_config": {"WOLF": 2, "BLESSED": 1, "SEER": 1, "WITCH": 1, "VILLAGER": 2},
        "max_runs": 8,
        "target_human_role": "受祝福者",
    },
    {
        "name": "7p-elder-2wolf-seer-witch-vill2",
        "total_players": 7,
        "num_wolves": 2,
        "role_config": {"WOLF": 2, "ELDER": 1, "SEER": 1, "WITCH": 1, "VILLAGER": 2},
        "max_runs": 8,
        "target_human_role": "长老",
    },
    {
        "name": "7p-cupid-2wolf-seer-witch-vill2",
        "total_players": 7,
        "num_wolves": 2,
        "role_config": {"WOLF": 2, "CUPID": 1, "SEER": 1, "WITCH": 1, "VILLAGER": 2},
        "max_runs": 8,
        "target_human_role": "丘比特",
    },
    {
        "name": "8p-mason-2wolf-seer-witch-mason2-vill2",
        "total_players": 8,
        "num_wolves": 2,
        "role_config": {"WOLF": 2, "MASON": 2, "SEER": 1, "WITCH": 1, "VILLAGER": 2},
        "max_runs": 4,
        "target_human_role": "共济会",
    },
    {
        "name": "7p-fox-2wolf-seer-witch-vill2",
        "total_players": 7,
        "num_wolves": 2,
        "role_config": {"WOLF": 2, "FOX": 1, "SEER": 1, "WITCH": 1, "VILLAGER": 2},
        "max_runs": 6,
        "target_human_role": "狐狸",
    },
    {
        "name": "7p-fox-clean-1wolf-seer-witch-vill3",
        "total_players": 7,
        "num_wolves": 1,
        "role_config": {"WOLF": 1, "FOX": 1, "SEER": 1, "WITCH": 1, "VILLAGER": 3},
        "max_runs": 6,
        "target_human_role": "狐狸",
    },
    {
        "name": "7p-angel-2wolf-seer-witch-vill2",
        "total_players": 7,
        "num_wolves": 2,
        "role_config": {"WOLF": 2, "ANGEL": 1, "SEER": 1, "WITCH": 1, "VILLAGER": 2},
        "max_runs": 6,
        "target_human_role": "天使",
    },
    {
        "name": "8p-scapegoat-2wolf-seer-witch-vill3",
        "total_players": 8,
        "num_wolves": 2,
        "role_config": {"WOLF": 2, "SCAPEGOAT": 1, "SEER": 1, "WITCH": 1, "VILLAGER": 3},
        "max_runs": 6,
        "target_human_role": "替罪羊",
    },
]


def extract_evidence(
    game_id: str,
    god_logs: list[dict[str, Any]],
    private_views: list[dict[str, Any]] | None = None,
    target_human_seat: int | None = None,
) -> dict[str, Any]:
    idiot_flip = next((log for log in god_logs if log.get("type") == "reveal" and "翻牌为白痴" in str(log.get("content"))), None)
    idiot_skip = next((log for log in god_logs if log.get("type") == "vote" and "无投票权" in str(log.get("content"))), None)
    super_saint_revenge = next((log for log in god_logs if log.get("type") == "super_saint"), None)
    wild_idol = next((log for log in god_logs if log.get("type") == "wild_child_action"), None)
    wild_awaken = next((log for log in god_logs if log.get("type") == "wild_child_awaken"), None)
    private_convert = next(
        (
            log
            for log in god_logs
            if log.get("type") == "system"
            and not log.get("is_public", True)
            and "秘密转化为狼人" in str(log.get("content"))
        ),
        None,
    )
    cursed_turn = next(
        (
            log
            for log in god_logs
            if log.get("type") == "system"
            and not log.get("is_public", True)
            and "秘密转入狼人阵营" in str(log.get("content"))
        ),
        None,
    )
    blessed_save = next(
        (
            log
            for log in god_logs
            if log.get("type") == "system" and "受祝福者抵挡了第一次狼人袭击" in str(log.get("content"))
        ),
        None,
    )
    elder_save = next(
        (
            log
            for log in god_logs
            if log.get("type") == "system" and "长老承受了第一次狼人袭击" in str(log.get("content"))
        ),
        None,
    )
    cupid_pair = next((log for log in god_logs if log.get("type") == "cupid_action"), None)
    lover_death = next(
        (
            log
            for log in god_logs
            if log.get("type") == "system" and "情侣殉情而死亡" in str(log.get("content"))
        ),
        None,
    )
    angel_victory = next((log for log in god_logs if log.get("type") == "angel_victory"), None)
    scapegoat_choice = next((log for log in god_logs if log.get("type") == "scapegoat_choice"), None)
    scapegoat_death = next(
        (
            log
            for log in god_logs
            if log.get("type") == "eliminate" and "替罪羊替死出局" in str(log.get("content"))
        ),
        None,
    )
    private_views = private_views or []
    target_view = next((view for view in private_views if int(view.get("seat") or 0) == int(target_human_seat or 0)), None)
    target_fox_checks = dict((target_view or {}).get("fox_checks") or {})
    fox_private_result = bool(target_view and str(target_view.get("role") or "") == "狐狸" and target_fox_checks)
    fox_power_active = bool((target_view or {}).get("fox_power_active", False))
    fox_clean_result = any(str(result) == "没有狼人" for result in target_fox_checks.values())
    fox_lost_power = bool(target_view and str(target_view.get("role") or "") == "狐狸" and target_fox_checks and not fox_power_active)
    non_fox_leak = next(
        (
            view
            for view in private_views
            if str(view.get("role") or "") != "狐狸" and ("fox_checks" in view or "fox_power_active" in view)
        ),
        None,
    )
    target_mason_peers = list((target_view or {}).get("mason_peers") or [])
    mason_private_info = bool(target_view and str(target_view.get("role") or "") == "共济会" and target_mason_peers)
    non_mason_leak = next(
        (
            view
            for view in private_views
            if str(view.get("role") or "") != "共济会" and "mason_peers" in view
        ),
        None,
    )
    return {
        "game_id": game_id,
        "idiot_flip": idiot_flip,
        "idiot_skip": idiot_skip,
        "super_saint_revenge": super_saint_revenge,
        "wild_idol": wild_idol,
        "wild_awaken": wild_awaken,
        "private_convert": private_convert,
        "cursed_turn": cursed_turn,
        "blessed_save": blessed_save,
        "elder_save": elder_save,
        "cupid_pair": cupid_pair,
        "lover_death": lover_death,
        "angel_victory": angel_victory,
        "scapegoat_choice": scapegoat_choice,
        "scapegoat_death": scapegoat_death,
        "fox_private_result": fox_private_result,
        "fox_power_active": fox_power_active,
        "fox_clean_result": fox_clean_result,
        "fox_lost_power": fox_lost_power,
        "fox_checks": target_fox_checks,
        "fox_nonmember_leak": non_fox_leak,
        "mason_private_info": mason_private_info,
        "mason_peer_seats": target_mason_peers,
        "mason_nonmember_leak": non_mason_leak,
    }


def scenario_hit_target(name: str, evidence: dict[str, Any]) -> bool:
    if "idiot" in name:
        return bool(evidence["idiot_flip"] and evidence["idiot_skip"])
    if "super-saint" in name:
        return bool(evidence["super_saint_revenge"])
    if "wildchild" in name:
        return bool(evidence["wild_idol"] and evidence["wild_awaken"] and evidence["private_convert"])
    if "cursed" in name:
        return bool(evidence["cursed_turn"])
    if "blessed" in name:
        return bool(evidence["blessed_save"])
    if "elder" in name:
        return bool(evidence["elder_save"])
    if "cupid" in name:
        return bool(evidence["cupid_pair"] and evidence["lover_death"])
    if "angel" in name:
        return bool(evidence["angel_victory"])
    if "scapegoat" in name:
        return bool(evidence["scapegoat_choice"] and evidence["scapegoat_death"])
    if "fox-clean" in name:
        return bool(evidence["fox_clean_result"] and evidence["fox_lost_power"] and not evidence["fox_nonmember_leak"])
    if "fox" in name:
        return bool(evidence["fox_private_result"] and not evidence["fox_nonmember_leak"])
    if "mason" in name:
        return bool(evidence["mason_private_info"] and not evidence["mason_nonmember_leak"])
    return False


def should_abort_low_signal_run(
    scenario_name: str,
    status: dict[str, Any],
    public_logs: list[dict[str, Any]],
    private_view: dict[str, Any] | None = None,
) -> bool:
    day = int(status.get("day_count") or 0)
    phase = str(status.get("phase") or "")
    claims = (status.get("day_summary") or {}).get("claims") or {}

    if "idiot" in scenario_name:
        if (
            private_view
            and str(private_view.get("role") or "") == "白痴"
            and bool(private_view.get("alive", False))
            and bool(private_view.get("revealed_role") == "白痴")
            and not bool(private_view.get("can_vote", True))
        ):
            return False
        if (
            private_view
            and str(private_view.get("role") or "") == "白痴"
            and bool(private_view.get("revealed_role") == "白痴")
            and not bool(private_view.get("can_vote", True))
        ):
            return False
        if private_view and str(private_view.get("role") or "") == "白痴" and not bool(private_view.get("alive", True)):
            return True
        if day >= 1 and phase == "vote":
            idiot_claims = claims.get("白痴") or []
            if not idiot_claims:
                return True

    if "wildchild" in scenario_name:
        if day >= 2:
            wildchild_logs = [log for log in public_logs if "野孩子" in str(log.get("content") or "")]
            if not wildchild_logs:
                return True

    if "super-saint" in scenario_name:
        if private_view and str(private_view.get("role") or "") == "圣徒" and not bool(private_view.get("alive", True)):
            return True

    if "cursed" in scenario_name:
        if private_view and str(private_view.get("role") or "") == "被诅咒者" and bool(private_view.get("cursed_turned")):
            return False

    if "blessed" in scenario_name:
        if private_view and str(private_view.get("role") or "") == "受祝福者" and bool(private_view.get("blessing_used")):
            return False

    if "elder" in scenario_name:
        if private_view and str(private_view.get("role") or "") == "长老" and int(private_view.get("elder_lives") or 0) < 2:
            return False
        if day >= 2 and private_view and str(private_view.get("role") or "") == "长老" and int(private_view.get("elder_lives") or 0) >= 2:
            return True

    if "fox" in scenario_name:
        if private_view and str(private_view.get("role") or "") == "狐狸" and dict(private_view.get("fox_checks") or {}):
            return False
        if day >= 2 and not bool(claims.get("狐狸") or []):
            return True

    if "angel" in scenario_name:
        if private_view and str(private_view.get("role") or "") == "天使" and not bool(private_view.get("alive", True)):
            return False
        if day >= 2 and private_view and str(private_view.get("role") or "") == "天使" and bool(private_view.get("alive", True)):
            return True

    if "scapegoat" in scenario_name:
        if private_view and str(private_view.get("role") or "") == "替罪羊" and not bool(private_view.get("alive", True)):
            return False
        if day >= 3 and private_view and str(private_view.get("role") or "") == "替罪羊" and bool(private_view.get("alive", True)):
            return True

    return False


def write_validation_report(scenario: dict[str, Any], results: list[dict[str, Any]]) -> Path:
    report_path = REPORT_ROOT / f"{scenario['name']}_validation.md"
    lines = [
        f"# {scenario['name']} 验证报告",
        "",
        f"- 最大尝试次数：{scenario['max_runs']}",
        f"- 实际尝试次数：{len(results)}",
        "",
    ]
    for item in results:
        evidence = item.get("evidence") or {}
        lines.extend(
            [
                f"## {item['game_id']}",
                f"- 命中目标：{'是' if item['hit_target'] else '否'}",
                f"- 白痴翻牌：{'是' if evidence.get('idiot_flip') else '否'}",
                f"- 白痴后续跳票：{'是' if evidence.get('idiot_skip') else '否'}",
                f"- 圣徒反噬：{'是' if evidence.get('super_saint_revenge') else '否'}",
                f"- 野孩子认榜样：{'是' if evidence.get('wild_idol') else '否'}",
                f"- 野孩子转狼：{'是' if evidence.get('wild_awaken') else '否'}",
                f"- 私有转化总结：{'是' if evidence.get('private_convert') else '否'}",
                f"- 被诅咒者转狼：{'是' if evidence.get('cursed_turn') else '否'}",
                f"- 受祝福者挡刀：{'是' if evidence.get('blessed_save') else '否'}",
                f"- 长老扛首刀：{'是' if evidence.get('elder_save') else '否'}",
                f"- 丘比特连线：{'是' if evidence.get('cupid_pair') else '否'}",
                f"- 情侣殉情：{'是' if evidence.get('lover_death') else '否'}",
                f"- 天使独立获胜：{'是' if evidence.get('angel_victory') else '否'}",
                f"- 替罪羊替死：{'是' if evidence.get('scapegoat_death') else '否'}",
                f"- 替罪羊指定限票：{'是' if evidence.get('scapegoat_choice') else '否'}",
                f"- 狐狸私有嗅探：{'是' if evidence.get('fox_private_result') else '否'}",
                f"- 狐狸能力仍在：{'是' if evidence.get('fox_power_active') else '否'}",
                f"- 狐狸命中无狼区域：{'是' if evidence.get('fox_clean_result') else '否'}",
                f"- 狐狸已失去能力：{'是' if evidence.get('fox_lost_power') else '否'}",
                f"- 非狐狸泄漏：{'是' if evidence.get('fox_nonmember_leak') else '否'}",
                f"- 共济会私有同伴：{'是' if evidence.get('mason_private_info') else '否'}",
                f"- 非共济会泄漏：{'是' if evidence.get('mason_nonmember_leak') else '否'}",
                "",
            ]
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def write_run_state(scenario_name: str, run_index: int, payload: dict[str, Any]) -> None:
    state_dir = REPORT_ROOT / scenario_name
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"run_{run_index:02d}_state.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_fast_seat_model_map(total_players: int) -> dict[str, str]:
    return {str(seat): FAST_MODEL for seat in range(1, total_players + 1)}


def find_target_human_seat(client: Any, game_id: str, target_role: str) -> tuple[int | None, dict[str, Any] | None]:
    players = batch.fetch_json(client, "GET", f"/api/game/{game_id}/players")
    for public_player in players:
        seat = int(public_player["seat"])
        private_view = batch.fetch_json(client, "GET", f"/api/game/{game_id}/player/{seat}")
        if str(private_view.get("role") or "") == target_role:
            return seat, private_view
    return None, None


def get_neighbor_triplet(seats: list[int], center_seat: int) -> list[int]:
    ordered = sorted(seats)
    if center_seat not in ordered:
        return [center_seat]
    if len(ordered) <= 2:
        return ordered
    idx = ordered.index(center_seat)
    return [ordered[(idx - 1) % len(ordered)], center_seat, ordered[(idx + 1) % len(ordered)]]


def infer_validation_human_action(
    scenario: dict[str, Any],
    action_type: str,
    private_view: dict[str, Any],
    public_logs: list[dict[str, Any]],
    status: dict[str, Any],
    memory: dict[str, Any],
    client: Any,
    game_id: str,
    target_human_seat: int,
) -> dict[str, Any]:
    role = str(private_view.get("role") or "")
    seat = int(private_view["seat"])

    if role == "白痴" and action_type == "speech":
        if bool(private_view.get("revealed_role") == "白痴") and not bool(private_view.get("can_vote", True)):
            target = next((int(item) for item in status.get("alive_seats", []) if int(item) != seat), None)
            return {
                "content": (
                    f"我是{seat}号，白痴已经翻牌了，我这轮没投票权。"
                    f"{'' if target is None else f' 我先继续听{target}号和后置位把逻辑讲完整。'}"
                    " 今天我更想看还握着投票的人怎么站边，不会再主动抢节奏。"
                )
            }
        target = next((int(item) for item in status.get("alive_seats", []) if int(item) != seat), None)
        claims = (status.get("day_summary") or {}).get("claims") or {}
        sole_seer_claims = [int(item) for item in (claims.get("预言家") or []) if int(item) != seat]
        if sole_seer_claims and target in sole_seer_claims:
            alternatives = [int(item) for item in status.get("alive_seats", []) if int(item) not in {seat, *sole_seer_claims}]
            if alternatives:
                target = alternatives[0]
        if target is None:
            return {"content": f"我是{seat}号，身份是白痴。"}
        return {
            "content": (
                f"我是{seat}号，身份是白痴。{target}号现在给我的感觉不太对，"
                "但我不想因为一句查杀或者一个人带票就直接站死边。"
                "你们可以继续听我这轮的判断，如果最后觉得我像抗推位也可以把票压到我身上，"
                "总之别用最省事的方式结束讨论。"
            )
        }

    if role == "白痴" and action_type == "vote":
        available = [int(item) for item in status.get("human_action_options", {}).get("candidates") or []]
        if not available:
            return {"target": None}
        if bool(private_view.get("revealed_role") == "白痴") and not bool(private_view.get("can_vote", True)):
            return {"target": available[0]}
        protected = set()
        claims = (status.get("day_summary") or {}).get("claims") or {}
        for role_name in ("预言家", "女巫", "守卫", "猎人"):
            for claimed in claims.get(role_name) or []:
                protected.add(int(claimed))
        non_protected = [seat_num for seat_num in available if seat_num not in protected]
        target = non_protected[0] if non_protected else available[0]
        return {"target": target}

    if role == "圣徒" and action_type == "speech":
        target = next((int(item) for item in status.get("alive_seats", []) if int(item) != seat), None)
        if target is None:
            return {"content": f"我是{seat}号，先按普通好人位聊。"}
        return {
            "content": (
                f"我是{seat}号，先把压力给到{target}号。"
                " 我不怕站到风口位，但今天别只拿状态打生打死。"
                " 如果你们觉得我像抗推位，可以把逻辑打满后再把票落到我身上，别用含糊站边混过去。"
            )
        }

    if role == "圣徒" and action_type == "vote":
        available = [int(item) for item in status.get("human_action_options", {}).get("candidates") or []]
        if not available:
            return {"target": None}
        claims = (status.get("day_summary") or {}).get("claims") or {}
        protected = {
            int(item)
            for role_name in ("预言家", "女巫", "守卫", "猎人")
            for item in (claims.get(role_name) or [])
        }
        non_protected = [seat_num for seat_num in available if seat_num not in protected]
        return {"target": non_protected[0] if non_protected else available[0]}

    if action_type == "witch_poison":
        available = [int(item) for item in status.get("human_action_options", {}).get("candidates") or []]
        if not available:
            return {"target": None}
        claims = (status.get("day_summary") or {}).get("claims") or {}
        idiot_claims = {int(item) for item in (claims.get("白痴") or [])}
        filtered = [seat_num for seat_num in available if seat_num not in idiot_claims]
        current_victim = status.get("human_action_options", {}).get("victim")
        if current_victim is not None:
            filtered = [seat_num for seat_num in filtered if seat_num != int(current_victim)]
        if "idiot" in str(scenario.get("name") or ""):
            filtered = [seat_num for seat_num in filtered if seat_num != target_human_seat]
        if any(tag in str(scenario.get("name") or "") for tag in ("cursed", "blessed")):
            filtered = [seat_num for seat_num in filtered if seat_num != target_human_seat]
        return {"target": filtered[0] if filtered else None}

    if action_type == "wolf":
        available = [int(item) for item in status.get("human_action_options", {}).get("candidates") or []]
        if not available:
            return {"target": None}
        claims = (status.get("day_summary") or {}).get("claims") or {}
        public_idiot_claims = {int(item) for item in (claims.get("白痴") or [])}
        safe_targets = [seat_num for seat_num in available if seat_num not in public_idiot_claims]
        if safe_targets:
            available = safe_targets

        flipped_idiot_targets: set[int] = set()
        for seat_num in list(available):
            seat_view = batch.fetch_json(client, "GET", f"/api/game/{game_id}/player/{seat_num}")
            if (
                str(seat_view.get("revealed_role") or "") == "白痴"
                and not bool(seat_view.get("can_vote", True))
            ):
                flipped_idiot_targets.add(seat_num)
        preserved_targets = [seat_num for seat_num in available if seat_num not in flipped_idiot_targets]
        if preserved_targets:
            available = preserved_targets

        scenario_name = str(scenario.get("name") or "")
        if "cursed" in scenario_name and target_human_seat in available:
            return {"target": target_human_seat}
        if "blessed" in scenario_name and target_human_seat in available:
            return {"target": target_human_seat}
        if "elder" in scenario_name and target_human_seat in available:
            return {"target": target_human_seat}
        if "scapegoat" in scenario_name:
            preserved = [seat_num for seat_num in available if seat_num != target_human_seat]
            if preserved:
                available = preserved

        action_status = dict(status)
        action_status["human_action_options"] = dict(status.get("human_action_options") or {})
        action_status["human_action_options"]["candidates"] = available
        return batch.infer_human_action(
            action_type,
            private_view,
            public_logs,
            action_status,
            memory,
        )

    if action_type == "witch_heal":
        victim = status.get("human_action_options", {}).get("victim")
        scenario_name = str(scenario.get("name") or "")
        if victim is not None and int(victim) == target_human_seat and any(tag in scenario_name for tag in ("cursed", "blessed")):
            return {"use_heal": False}
        return batch.infer_human_action(
            action_type,
            private_view,
            public_logs,
            status,
            memory,
        )

    if role == "野孩子" and action_type == "speech":
        target = next((int(item) for item in status.get("alive_seats", []) if int(item) != seat), None)
        if target is None:
            return {"content": f"我是{seat}号，身份是村民。"}
        return {
            "content": (
                f"我是{seat}号，身份先按普通好人位聊。"
                f" 这轮我先追问{target}号，重点看谁在抢节奏却不给理由。"
                " 如果后置位有人只讲态度不讲逻辑，我会直接把票挂过去。"
            )
        }

    if role == "被诅咒者" and action_type == "speech":
        target = next((int(item) for item in status.get("alive_seats", []) if int(item) != seat), None)
        if target is None:
            return {"content": f"我是{seat}号，先按普通好人位聊。"}
        return {
            "content": (
                f"我是{seat}号，先按普通好人位聊。"
                f" 这轮我先盯{target}号，看他是不是一直在借模糊话术躲判断。"
                " 我不想轻易跟着单点带票，谁真在偷节奏我再下重锤。"
            )
        }

    if role == "被诅咒者" and action_type == "vote":
        available = [int(item) for item in status.get("human_action_options", {}).get("candidates") or []]
        if not available:
            return {"target": None}
        claims = (status.get("day_summary") or {}).get("claims") or {}
        protected = {
            int(item)
            for role_name in ("预言家", "女巫", "守卫", "猎人")
            for item in (claims.get(role_name) or [])
        }
        non_protected = [seat_num for seat_num in available if seat_num not in protected]
        return {"target": non_protected[0] if non_protected else available[0]}

    if role == "受祝福者" and action_type == "speech":
        target = next((int(item) for item in status.get("alive_seats", []) if int(item) != seat), None)
        if target is None:
            return {"content": f"我是{seat}号，先按普通好人位聊。"}
        return {
            "content": (
                f"我是{seat}号，先把注意力放在{target}号。"
                " 这轮我主要看谁发言像在给自己留后手、又想把票型搅浑。"
                " 今天别图省事乱推，至少把每个人的落点讲清楚。"
            )
        }

    if role == "受祝福者" and action_type == "vote":
        available = [int(item) for item in status.get("human_action_options", {}).get("candidates") or []]
        if not available:
            return {"target": None}
        claims = (status.get("day_summary") or {}).get("claims") or {}
        protected = {
            int(item)
            for role_name in ("预言家", "女巫", "守卫", "猎人")
            for item in (claims.get(role_name) or [])
        }
        non_protected = [seat_num for seat_num in available if seat_num not in protected]
        return {"target": non_protected[0] if non_protected else available[0]}

    if role == "丘比特" and action_type == "cupid":
        available = [int(item) for item in status.get("human_action_options", {}).get("candidates") or []]
        if len(available) < 2:
            return {"pair": []}
        non_self = [seat_num for seat_num in available if seat_num != seat]
        if len(non_self) >= 2:
            return {"pair": non_self[:2]}
        return {"pair": available[:2]}

    if role == "共济会" and action_type == "speech":
        target = next((int(item) for item in status.get("alive_seats", []) if int(item) != seat), None)
        if target is None:
            return {"content": f"我是{seat}号，先按普通好人位聊。"}
        return {
            "content": (
                f"我是{seat}号，先按普通好人位聊。"
                f" 这轮我先观察{target}号后续是不是只给态度不给逻辑。"
                " 现在信息不够满，我不会强拉单边，但会优先盯那些抢节奏又不解释的人。"
            )
        }

    if role == "共济会" and action_type == "vote":
        available = [int(item) for item in status.get("human_action_options", {}).get("candidates") or []]
        if not available:
            return {"target": None}
        peer_set = {int(item) for item in (private_view.get("mason_peers") or [])}
        non_peer = [seat_num for seat_num in available if seat_num not in peer_set]
        return {"target": non_peer[0] if non_peer else available[0]}

    if role == "天使" and action_type == "speech":
        target = next((int(item) for item in status.get("alive_seats", []) if int(item) != seat), None)
        if target is None:
            return {"content": f"我是{seat}号，先按普通好人位聊。"}
        return {
            "content": (
                f"我是{seat}号，先把压力给到{target}号。"
                " 我这轮不想玩模糊站边，谁最像顺势带票、谁最像蹭发言热度，我就先点谁。"
                " 如果你们觉得我有问题，也别留到后面，今天就把票型摊开。"
            )
        }

    if role == "天使" and action_type == "vote":
        available = [int(item) for item in status.get("human_action_options", {}).get("candidates") or []]
        if not available:
            return {"target": None}
        non_self = [seat_num for seat_num in available if seat_num != seat]
        return {"target": non_self[0] if non_self else available[0]}

    if role == "替罪羊" and action_type == "speech":
        target = next((int(item) for item in status.get("alive_seats", []) if int(item) != seat), None)
        if target is None:
            return {"content": f"我是{seat}号，先按普通好人位聊。"}
        return {
            "content": (
                f"我是{seat}号，今天我先盯{target}号。"
                " 我不接受平空态度混过去，谁最像在等别人先拍板，我就优先追问谁。"
                " 这轮如果要出人，至少把每个人的票理由讲清楚。"
            )
        }

    if role == "替罪羊" and action_type == "vote":
        available = [int(item) for item in status.get("human_action_options", {}).get("candidates") or []]
        if not available:
            return {"target": None}
        claims = (status.get("day_summary") or {}).get("claims") or {}
        protected = {
            int(item)
            for role_name in ("预言家", "女巫", "守卫", "猎人")
            for item in (claims.get(role_name) or [])
        }
        non_protected = [seat_num for seat_num in available if seat_num not in protected]
        return {"target": non_protected[0] if non_protected else available[0]}

    if role == "替罪羊" and action_type == "scapegoat":
        available = [int(item) for item in status.get("human_action_options", {}).get("candidates") or []]
        if not available:
            return {"allowed_voters": []}
        return {"allowed_voters": available[: max(1, min(2, len(available)))]}

    if role == "狐狸" and action_type == "fox":
        available = [int(item) for item in status.get("human_action_options", {}).get("candidates") or []]
        if not available:
            return {"target": None}
        if "fox-clean" in str(scenario.get("name") or ""):
            seat_views = {
                seat_num: batch.fetch_json(client, "GET", f"/api/game/{game_id}/player/{seat_num}")
                for seat_num in status.get("alive_seats") or []
            }
            alive_seats = [int(item) for item in status.get("alive_seats") or []]
            for candidate in available:
                triplet = get_neighbor_triplet(alive_seats, int(candidate))
                if all(str((seat_views.get(triplet_seat) or {}).get("camp") or "") != "狼人阵营" for triplet_seat in triplet):
                    return {"target": int(candidate)}
        unchecked = [
            seat_num for seat_num in available
            if str(seat_num) not in {str(key) for key in dict(private_view.get("fox_checks") or {}).keys()}
        ]
        return {"target": unchecked[0] if unchecked else available[0]}

    if role == "狐狸" and action_type == "speech":
        target = next((int(item) for item in status.get("alive_seats", []) if int(item) != seat), None)
        if target is None:
            return {"content": f"我是{seat}号，先按普通好人位聊。"}
        return {
            "content": (
                f"我是{seat}号，先把注意力放在{target}号。"
                " 这轮我更在意谁在利用模糊发言给自己留退路，谁又在顺手蹭票型。"
                " 先把逻辑链摊开聊，别靠一句态度就把人硬推走。"
            )
        }

    if role == "狐狸" and action_type == "vote":
        available = [int(item) for item in status.get("human_action_options", {}).get("candidates") or []]
        if not available:
            return {"target": None}
        claims = (status.get("day_summary") or {}).get("claims") or {}
        protected = {
            int(item)
            for role_name in ("预言家", "女巫", "守卫", "猎人")
            for item in (claims.get(role_name) or [])
        }
        non_protected = [seat_num for seat_num in available if seat_num not in protected]
        return {"target": non_protected[0] if non_protected else available[0]}

    return batch.infer_human_action(action_type, private_view, public_logs, status, memory)


def infer_waiting_seat_action(
    scenario: dict[str, Any],
    waiting_seat: int,
    target_human_seat: int,
    action_type: str,
    public_logs: list[dict[str, Any]],
    status: dict[str, Any],
    memory_by_seat: dict[int, dict[str, Any]],
    client: Any,
    game_id: str,
) -> dict[str, Any]:
    private_view = batch.fetch_json(client, "GET", f"/api/game/{game_id}/player/{waiting_seat}")
    seat_memory = memory_by_seat.setdefault(waiting_seat, {})

    def build_scapegoat_tie_vote() -> dict[str, Any]:
        alive = sorted(int(item) for item in status.get("alive_seats") or [])
        available = [int(item) for item in status.get("human_action_options", {}).get("candidates") or []]
        if len(alive) < 4 or not available:
            return {"target": available[0] if available else None}

        voters = list(alive)
        targets = [seat_num for seat_num in alive if seat_num != target_human_seat]
        if len(targets) < 2:
            return {"target": available[0] if available else None}

        target_sizes = [len(voters) // 2, len(voters) // 2]
        if len(voters) % 2 == 1:
            target_sizes.append(1)
        chosen_targets = targets[: len(target_sizes)]
        assignment: dict[int, int] = {}

        def search(voter_index: int, remaining: list[int]) -> bool:
            if voter_index >= len(voters):
                return all(count == 0 for count in remaining)
            voter = voters[voter_index]
            for target_index, target in enumerate(chosen_targets):
                if remaining[target_index] <= 0 or target == voter:
                    continue
                remaining[target_index] -= 1
                assignment[voter] = target
                if search(voter_index + 1, remaining):
                    return True
                remaining[target_index] += 1
                assignment.pop(voter, None)
            return False

        if not search(0, target_sizes[:]):
            fallback = next((seat_num for seat_num in available if seat_num != waiting_seat), None)
            return {"target": fallback if fallback is not None else available[0]}
        preferred = assignment.get(waiting_seat)
        if preferred in available:
            return {"target": preferred}
        fallback = next((seat_num for seat_num in available if seat_num != waiting_seat), None)
        return {"target": fallback if fallback is not None else available[0]}

    if "angel" in str(scenario.get("name") or "") and action_type == "vote" and waiting_seat != target_human_seat:
        return {"target": target_human_seat}
    if "scapegoat" in str(scenario.get("name") or "") and action_type == "vote":
        return build_scapegoat_tie_vote()
    if waiting_seat == target_human_seat or action_type in {"wolf", "witch_poison"}:
        return infer_validation_human_action(
            scenario,
            action_type,
            private_view,
            public_logs,
            status,
            seat_memory,
            client,
            game_id,
            target_human_seat,
        )
    return batch.infer_human_action(
        action_type,
        private_view,
        public_logs,
        status,
        seat_memory,
    )


def ensure_fast_server():
    pkill_patterns = [
        "python app.py",
        "./.venv/bin/python app.py",
        f"{ROOT}/app.py",
        f"{ROOT}/.venv/bin/python app.py",
    ]
    for pattern in pkill_patterns:
        subprocess.run(
            ["pkill", "-f", pattern],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    time.sleep(1.0)
    original_default = batch.os.environ.get("WEREWOLF_API_DEFAULT_TIMEOUT")
    original_model_timeouts = batch.os.environ.get("WEREWOLF_API_MODEL_TIMEOUTS")
    batch.os.environ["WEREWOLF_API_DEFAULT_TIMEOUT"] = FAST_DEFAULT_TIMEOUT
    batch.os.environ["WEREWOLF_API_MODEL_TIMEOUTS"] = FAST_MODEL_TIMEOUTS
    try:
        env = os.environ.copy()
        env["WEREWOLF_API_DEFAULT_TIMEOUT"] = FAST_DEFAULT_TIMEOUT
        env["WEREWOLF_API_MODEL_TIMEOUTS"] = FAST_MODEL_TIMEOUTS
        env["WEREWOLF_API_KEY"] = batch.API_KEY
        env["WEREWOLF_API_BASE_URL"] = batch.API_BASE
        env["WEREWOLF_ADMIN_PASSWORD"] = batch.ADMIN_PASSWORD
        process = subprocess.Popen(
            [str(batch.VENV_PYTHON), "app.py"],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        client = batch.httpx.Client(timeout=30.0)
        for _ in range(60):
            try:
                response = client.get(f"{batch.BASE_URL}/")
                response.raise_for_status()
                return process, client
            except Exception:
                time.sleep(1.0)
        batch.stop_server(process)
        client.close()
        raise RuntimeError("Fresh validation backend did not become ready within 60 seconds")
    finally:
        if original_default is None:
            batch.os.environ.pop("WEREWOLF_API_DEFAULT_TIMEOUT", None)
        else:
            batch.os.environ["WEREWOLF_API_DEFAULT_TIMEOUT"] = original_default
        if original_model_timeouts is None:
            batch.os.environ.pop("WEREWOLF_API_MODEL_TIMEOUTS", None)
        else:
            batch.os.environ["WEREWOLF_API_MODEL_TIMEOUTS"] = original_model_timeouts


def ensure_role_catalog_contains(
    process: Any,
    client: Any,
    role_code: str,
    role_name: str,
) -> tuple[Any, Any]:
    try:
        roles = batch.fetch_json(client, "GET", "/api/config/roles")
    except Exception:
        roles = []
    if any(str(item.get("code") or "") == role_code and str(item.get("name") or "") == role_name for item in roles):
        return process, client
    client.close()
    batch.stop_server(process)
    process, client = ensure_fast_server()
    roles = batch.fetch_json(client, "GET", "/api/config/roles")
    if any(str(item.get("code") or "") == role_code and str(item.get("name") or "") == role_name for item in roles):
        return process, client
    raise RuntimeError(f"role catalog missing after restart: {role_code}/{role_name}")


def run_validation_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    scenario_report_dir = REPORT_ROOT / scenario["name"]
    scenario_report_dir.mkdir(parents=True, exist_ok=True)
    for run_index in range(1, scenario["max_runs"] + 1):
        process, client = ensure_fast_server()
        try:
            target_role_name = str(scenario.get("target_human_role") or "")
            role_code_hint = next(
                (
                    code
                    for code, role_name in (
                        ("IDIOT", "白痴"),
                        ("SUPER_SAINT", "圣徒"),
                        ("WILD_CHILD", "野孩子"),
                        ("ELDER", "长老"),
                        ("CURSED", "被诅咒者"),
                        ("BLESSED", "受祝福者"),
                        ("CUPID", "丘比特"),
                        ("MASON", "共济会"),
                        ("FOX", "狐狸"),
                        ("ANGEL", "天使"),
                        ("SCAPEGOAT", "替罪羊"),
                    )
                    if role_name == target_role_name
                ),
                "",
            )
            if role_code_hint:
                process, client = ensure_role_catalog_contains(process, client, role_code_hint, target_role_name)
            game_id = ""
            matched_role = False
            human_seat: int | None = None
            for reroll in range(1, 13):
                created = batch.fetch_json(
                    client,
                    "POST",
                    "/api/game/create",
                    json={
                        "human_seats": [seat for seat in range(1, scenario["total_players"] + 1)],
                        "total_players": scenario["total_players"],
                        "num_wolves": scenario["num_wolves"],
                        "role_config": scenario["role_config"],
                        "random_models": False,
                        "seat_model_map": build_fast_seat_model_map(scenario["total_players"]),
                        "god_mode": {"enabled": True, "password": batch.GOD_PASSWORD},
                    },
                )
                game_id = created["game_id"]
                human_seat, player_view = find_target_human_seat(
                    client,
                    game_id,
                    str(scenario.get("target_human_role") or ""),
                )
                current_role = str((player_view or {}).get("role") or "")
                write_run_state(
                    scenario["name"],
                    run_index,
                    {
                        "stage": "created",
                        "game_id": game_id,
                        "reroll": reroll,
                        "human_seat": human_seat,
                        "human_role": current_role,
                    },
                )
                if human_seat is not None and current_role == str(scenario.get("target_human_role") or ""):
                    matched_role = True
                    break
            if not matched_role:
                raise RuntimeError(
                    f"role reroll exhausted: expected {scenario.get('target_human_role')} for {scenario['name']}"
                )
            batch.fetch_json(client, "POST", f"/api/game/{game_id}/start")
            write_run_state(
                scenario["name"],
                run_index,
                {"stage": "started", "game_id": game_id, "human_seat": human_seat},
            )
            assert human_seat is not None
            memory_by_seat: dict[int, dict[str, Any]] = {}
            started_at = time.time()
            while True:
                if time.time() - started_at > batch.SCENARIO_TIMEOUT_SECONDS:
                    raise TimeoutError(f"场景在 {batch.SCENARIO_TIMEOUT_SECONDS} 秒后超时：{scenario['name']} / {game_id}")
                status = batch.fetch_json(client, "GET", f"/api/game/{game_id}/status")
                if status.get("phase") == "ended":
                    break
                public_payload = batch.fetch_json(client, "GET", f"/api/game/{game_id}/log?limit=500")
                current_private_view = batch.fetch_json(client, "GET", f"/api/game/{game_id}/player/{human_seat}")
                if should_abort_low_signal_run(
                    scenario["name"],
                    status,
                    public_payload.get("logs", []),
                    current_private_view,
                ):
                    raise RuntimeError(f"low-signal abort: {scenario['name']} / {game_id}")
                waiting_seat = int(status.get("waiting_for_human") or 0)
                if waiting_seat:
                    action = infer_waiting_seat_action(
                        scenario,
                        waiting_seat,
                        human_seat,
                        str(status.get("human_action_type")),
                        public_payload.get("logs", []),
                        status,
                        memory_by_seat,
                        client,
                        game_id,
                    )
                    batch.fetch_json(
                        client,
                        "POST",
                        f"/api/game/{game_id}/action",
                        json={"action_type": status.get("human_action_type"), "data": action},
                    )
                    time.sleep(0.2)
                    continue
                time.sleep(1.0)

            game_detail = batch.fetch_json(client, "GET", f"/api/stats/game/{game_id}")
            god_logs_payload = batch.fetch_json(
                client,
                "GET",
                f"/api/game/{game_id}/god-mode/logs?password={batch.GOD_PASSWORD}&limit=1000",
            )
            result = batch.review_game(
                scenario=scenario,
                game_id=game_id,
                players=game_detail["players"],
                public_logs=game_detail.get("public_logs") or game_detail.get("logs") or [],
                private_logs=game_detail.get("private_logs") or god_logs_payload.get("logs") or [],
                human_seat=human_seat,
                report_dir=scenario_report_dir,
            )
            god_logs = batch.fetch_json(
                client,
                "GET",
                f"/api/game/{result['game_id']}/god-mode/logs?password={batch.GOD_PASSWORD}&limit=1000",
            ).get("logs", [])
            private_views = [
                batch.fetch_json(client, "GET", f"/api/game/{result['game_id']}/player/{seat_data['seat']}")
                for seat_data in game_detail["players"]
            ]
            evidence = extract_evidence(
                result["game_id"],
                god_logs,
                private_views=private_views,
                target_human_seat=human_seat,
            )
            hit_target = scenario_hit_target(scenario["name"], evidence)
            results.append(
                {
                    "game_id": result["game_id"],
                    "report_path": result["report_path"],
                    "winner": result["winner"],
                    "evidence": evidence,
                    "hit_target": hit_target,
                }
            )
            write_run_state(
                scenario["name"],
                run_index,
                {
                    "stage": "completed",
                    "game_id": result["game_id"],
                    "human_seat": human_seat,
                    "hit_target": hit_target,
                },
            )
            write_validation_report(scenario, results)
            if hit_target:
                break
        except Exception as exc:
            write_run_state(
                scenario["name"],
                run_index,
                {"stage": "error", "error": str(exc)},
            )
            results.append(
                {
                    "game_id": f"run_{run_index}_error",
                    "report_path": "",
                    "winner": f"ERROR: {exc}",
                    "evidence": {
                        "game_id": f"run_{run_index}_error",
                        "idiot_flip": None,
                        "idiot_skip": None,
                        "super_saint_revenge": None,
                        "wild_idol": None,
                        "wild_awaken": None,
                        "private_convert": None,
                        "cursed_turn": None,
                        "blessed_save": None,
                        "cupid_pair": None,
                        "lover_death": None,
                        "angel_victory": None,
                        "scapegoat_choice": None,
                        "scapegoat_death": None,
                        "fox_private_result": None,
                        "fox_power_active": None,
                        "fox_clean_result": None,
                        "fox_lost_power": None,
                        "fox_checks": {},
                        "fox_nonmember_leak": None,
                        "mason_private_info": None,
                        "mason_peer_seats": [],
                        "mason_nonmember_leak": None,
                    },
                    "hit_target": False,
                }
            )
            write_validation_report(scenario, results)
        finally:
            client.close()
            batch.stop_server(process)
            time.sleep(1.0)
    validation_report = write_validation_report(scenario, results)
    return {
        "scenario": scenario["name"],
        "attempts": len(results),
        "hit_target": any(item["hit_target"] for item in results),
        "validation_report": str(validation_report),
        "results": results,
    }


def main() -> int:
    scenario_filter = {
        item.strip()
        for item in str(os.environ.get("VALIDATION_SCENARIOS") or "").split(",")
        if item.strip()
    }
    selected = [scenario for scenario in SCENARIOS if not scenario_filter or scenario["name"] in scenario_filter]
    summaries = [run_validation_scenario(scenario) for scenario in selected]
    print(json.dumps({"report_root": str(REPORT_ROOT), "summaries": summaries}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
