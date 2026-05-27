#!/usr/bin/env python3
"""
Run isolated live-flow validation for extension-role scenarios until key evidence appears.
"""

from __future__ import annotations

import json
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
        "name": "7p-super-saint-2wolf-seer-witch-vill2",
        "total_players": 7,
        "num_wolves": 2,
        "role_config": {"WOLF": 2, "SUPER_SAINT": 1, "SEER": 1, "WITCH": 1, "VILLAGER": 2},
        "max_runs": 8,
        "target_human_role": "圣徒",
    },
]


def extract_evidence(game_id: str, god_logs: list[dict[str, Any]]) -> dict[str, Any]:
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
    return {
        "game_id": game_id,
        "idiot_flip": idiot_flip,
        "idiot_skip": idiot_skip,
        "super_saint_revenge": super_saint_revenge,
        "wild_idol": wild_idol,
        "wild_awaken": wild_awaken,
        "private_convert": private_convert,
    }


def scenario_hit_target(name: str, evidence: dict[str, Any]) -> bool:
    if "idiot" in name:
        return bool(evidence["idiot_flip"] and evidence["idiot_skip"])
    if "super-saint" in name:
        return bool(evidence["super_saint_revenge"])
    if "wildchild" in name:
        return bool(evidence["wild_idol"] and evidence["wild_awaken"] and evidence["private_convert"])
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
        lines.extend(
            [
                f"## {item['game_id']}",
                f"- 命中目标：{'是' if item['hit_target'] else '否'}",
                f"- 白痴翻牌：{'是' if item['evidence']['idiot_flip'] else '否'}",
                f"- 白痴后续跳票：{'是' if item['evidence']['idiot_skip'] else '否'}",
                f"- 圣徒反噬：{'是' if item['evidence']['super_saint_revenge'] else '否'}",
                f"- 野孩子认榜样：{'是' if item['evidence']['wild_idol'] else '否'}",
                f"- 野孩子转狼：{'是' if item['evidence']['wild_awaken'] else '否'}",
                f"- 私有转化总结：{'是' if item['evidence']['private_convert'] else '否'}",
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
    original_default = batch.os.environ.get("WEREWOLF_API_DEFAULT_TIMEOUT")
    original_model_timeouts = batch.os.environ.get("WEREWOLF_API_MODEL_TIMEOUTS")
    batch.os.environ["WEREWOLF_API_DEFAULT_TIMEOUT"] = FAST_DEFAULT_TIMEOUT
    batch.os.environ["WEREWOLF_API_MODEL_TIMEOUTS"] = FAST_MODEL_TIMEOUTS
    try:
        return batch.ensure_server()
    finally:
        if original_default is None:
            batch.os.environ.pop("WEREWOLF_API_DEFAULT_TIMEOUT", None)
        else:
            batch.os.environ["WEREWOLF_API_DEFAULT_TIMEOUT"] = original_default
        if original_model_timeouts is None:
            batch.os.environ.pop("WEREWOLF_API_MODEL_TIMEOUTS", None)
        else:
            batch.os.environ["WEREWOLF_API_MODEL_TIMEOUTS"] = original_model_timeouts


def run_validation_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    scenario_report_dir = REPORT_ROOT / scenario["name"]
    scenario_report_dir.mkdir(parents=True, exist_ok=True)
    for run_index in range(1, scenario["max_runs"] + 1):
        process, client = ensure_fast_server()
        try:
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
            evidence = extract_evidence(result["game_id"], god_logs)
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
                        "wild_idol": None,
                        "wild_awaken": None,
                        "private_convert": None,
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
    summaries = [run_validation_scenario(scenario) for scenario in SCENARIOS]
    print(json.dumps({"report_root": str(REPORT_ROOT), "summaries": summaries}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
