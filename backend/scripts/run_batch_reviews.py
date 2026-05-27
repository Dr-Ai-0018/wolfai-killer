#!/usr/bin/env python3
"""
Run a batch of werewolf games, participate as one human seat, and write per-game markdown reviews.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import textwrap
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

import httpx


ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
BASE_URL = os.getenv("WEREWOLF_LOCAL_BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("WEREWOLF_API_KEY", "")
API_BASE = os.getenv("WEREWOLF_API_BASE_URL", "https://api.killerbest.com/v1")
ADMIN_PASSWORD = os.getenv("WEREWOLF_ADMIN_PASSWORD", "")
GOD_PASSWORD = os.getenv("WEREWOLF_GOD_PASSWORD", "gm-batch-review")
REPORT_ROOT = ROOT / "data" / "reports" / f"batch_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
MODELS = ["gpt-5.4-mini", "gpt-5.4", "gpt-5.3-codex", "gpt-5.2"]
SCENARIO_TIMEOUT_SECONDS = 240

RECOMMENDED_SCENARIOS: list[dict[str, Any]] = [
    {"name": "5p-single-wolf-witch", "total_players": 5, "num_wolves": 1, "role_config": {"WOLF": 1, "SEER": 1, "WITCH": 1, "HUNTER": 1, "VILLAGER": 1}},
    {"name": "5p-single-wolf-guard", "total_players": 5, "num_wolves": 1, "role_config": {"WOLF": 1, "SEER": 1, "GUARD": 1, "HUNTER": 1, "VILLAGER": 1}},
    {"name": "6p-standard-guard", "total_players": 6, "num_wolves": 2, "role_config": {"WOLF": 2, "SEER": 1, "WITCH": 1, "GUARD": 1, "VILLAGER": 1}},
    {"name": "6p-hunter-guard", "total_players": 6, "num_wolves": 2, "role_config": {"WOLF": 2, "SEER": 1, "HUNTER": 1, "GUARD": 1, "VILLAGER": 1}},
    {"name": "6p-witch-hunter", "total_players": 6, "num_wolves": 2, "role_config": {"WOLF": 2, "SEER": 1, "WITCH": 1, "HUNTER": 1, "VILLAGER": 1}},
    {"name": "7p-double-villager", "total_players": 7, "num_wolves": 2, "role_config": {"WOLF": 2, "SEER": 1, "WITCH": 1, "GUARD": 1, "VILLAGER": 2}},
    {"name": "7p-hunter-witch", "total_players": 7, "num_wolves": 2, "role_config": {"WOLF": 2, "SEER": 1, "WITCH": 1, "HUNTER": 1, "VILLAGER": 2}},
    {"name": "7p-full-core", "total_players": 7, "num_wolves": 2, "role_config": {"WOLF": 2, "SEER": 1, "WITCH": 1, "GUARD": 1, "HUNTER": 1, "VILLAGER": 1}},
    {"name": "8p-core-plus-two-villagers", "total_players": 8, "num_wolves": 2, "role_config": {"WOLF": 2, "SEER": 1, "WITCH": 1, "GUARD": 1, "HUNTER": 1, "VILLAGER": 2}},
    {"name": "8p-guard-heavy", "total_players": 8, "num_wolves": 2, "role_config": {"WOLF": 2, "SEER": 1, "WITCH": 1, "GUARD": 1, "VILLAGER": 3}},
    {"name": "9p-longer-balanced", "total_players": 9, "num_wolves": 2, "role_config": {"WOLF": 2, "SEER": 1, "WITCH": 1, "GUARD": 1, "HUNTER": 1, "VILLAGER": 3}},
]

FIVE_PLAYER_VALIDATION_SCENARIOS: list[dict[str, Any]] = [
    {"name": "5p-validation-single-wolf-witch", "total_players": 5, "num_wolves": 1, "role_config": {"WOLF": 1, "SEER": 1, "WITCH": 1, "HUNTER": 1, "VILLAGER": 1}},
    {"name": "5p-validation-single-wolf-guard", "total_players": 5, "num_wolves": 1, "role_config": {"WOLF": 1, "SEER": 1, "GUARD": 1, "HUNTER": 1, "VILLAGER": 1}},
]

SCENARIOS: list[dict[str, Any]] = list(RECOMMENDED_SCENARIOS)
SERVER_RECOVERY_RETRIES = 2


def require_env(name: str, value: str) -> str:
    if value.strip():
        return value
    raise RuntimeError(f"缺少环境变量 {name}")


def ensure_server() -> tuple[Optional[subprocess.Popen[str]], httpx.Client]:
    api_key = require_env("WEREWOLF_API_KEY", API_KEY)
    admin_password = require_env("WEREWOLF_ADMIN_PASSWORD", ADMIN_PASSWORD)
    client = httpx.Client(timeout=30.0)
    try:
        response = client.get(f"{BASE_URL}/")
        response.raise_for_status()
        return None, client
    except Exception:
        env = os.environ.copy()
        env["WEREWOLF_API_KEY"] = api_key
        env["WEREWOLF_API_BASE_URL"] = API_BASE
        env["WEREWOLF_ADMIN_PASSWORD"] = admin_password
        process = subprocess.Popen(
            [str(VENV_PYTHON), "app.py"],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        for _ in range(60):
            try:
                response = client.get(f"{BASE_URL}/")
                response.raise_for_status()
                return process, client
            except Exception:
                time.sleep(1)
        raise RuntimeError("本地后端在 60 秒内未能完成启动")


def stop_server(process: Optional[subprocess.Popen[str]]) -> None:
    if process is None:
        return
    process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def fetch_json(client: httpx.Client, method: str, path: str, **kwargs: Any) -> Any:
    response = client.request(method, f"{BASE_URL}{path}", **kwargs)
    response.raise_for_status()
    return response.json()


def is_recoverable_server_error(exc: Exception) -> bool:
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    if isinstance(exc, httpx.RequestError):
        message = str(exc).lower()
        return "connection refused" in message or "server disconnected" in message
    return False


def restart_server(
    process: Optional[subprocess.Popen[str]],
    client: httpx.Client,
) -> tuple[Optional[subprocess.Popen[str]], httpx.Client]:
    client.close()
    stop_server(process)
    return ensure_server()


def build_seat_model_map(total_players: int, offset: int) -> dict[str, str]:
    return {str(seat): MODELS[(seat - 1 + offset) % len(MODELS)] for seat in range(1, total_players + 1)}


def infer_human_action(
    action_type: str,
    private_view: dict[str, Any],
    public_logs: list[dict[str, Any]],
    status: dict[str, Any],
    memory: dict[str, Any],
) -> dict[str, Any]:
    seat = int(private_view["seat"])
    role = private_view.get("role")
    teammates = set(int(item) for item in memory.get("wolf_teammates", []))
    known_results = private_view.get("seer_results") or {}
    current_votes = status.get("human_action_options", {}).get("current_votes") or {}
    candidates = [int(item) for item in status.get("human_action_options", {}).get("candidates") or []]
    alive_seats = [int(item) for item in status.get("alive_seats") or [] if int(item) != seat]
    memory.setdefault("day_pressure_target", None)
    memory.setdefault("last_public_claims", {})

    def score_candidates() -> dict[int, int]:
        scores = {candidate: 0 for candidate in candidates or alive_seats}
        public_claims: dict[str, list[int]] = {}
        for log in public_logs[-40:]:
            content = str(log.get("content") or "")
            log_seat = int(log.get("seat") or 0)
            meta = log.get("meta") or {}
            claimed_role = meta.get("claimed_role")
            if log.get("type") == "speech" and claimed_role:
                public_claims.setdefault(str(claimed_role), [])
                if log_seat and log_seat not in public_claims[str(claimed_role)]:
                    public_claims[str(claimed_role)].append(log_seat)
            for candidate in scores:
                if f"{candidate}号" in content:
                    scores[candidate] += 1
                    if log.get("type") == "speech":
                        scores[candidate] += 1
                if log.get("type") == "vote" and log_seat == candidate:
                    scores[candidate] += 1
            if log.get("type") == "vote":
                target = int(((log.get("meta") or {}).get("target")) or 0)
                voter = int(((log.get("meta") or {}).get("voter")) or 0)
                if target == seat and voter in scores:
                    scores[voter] += 3
        for checked_seat_raw, result in known_results.items():
            checked_seat = int(checked_seat_raw)
            if checked_seat in scores and result == "狼人":
                scores[checked_seat] += 100
            elif checked_seat in scores and result == "好人":
                scores[checked_seat] -= 100
        for role_name, seats in public_claims.items():
            if len(seats) == 1 and role_name in {"预言家", "女巫", "守卫", "猎人"}:
                claimed_seat = int(seats[0])
                if claimed_seat in scores and "狼" not in str(private_view.get("camp")):
                    scores[claimed_seat] -= 12
        for teammate in teammates:
            if teammate in scores:
                scores[teammate] -= 100
        return scores

    def best_suspicion_target(exclude: Optional[set[int]] = None) -> Optional[int]:
        exclude = exclude or set()
        scores = score_candidates()
        eligible = [candidate for candidate in scores if candidate not in exclude and candidate != seat]
        if not eligible:
            return None
        return max(eligible, key=lambda item: (scores[item], -item))

    def best_non_teammate(exclude: Optional[set[int]] = None) -> Optional[int]:
        exclude = exclude or set()
        for candidate in candidates or alive_seats:
            if candidate not in exclude and candidate not in teammates and candidate != seat:
                return candidate
        return None

    if action_type == "wolf":
        teammates_from_options = status.get("human_action_options", {}).get("teammates") or []
        memory["wolf_teammates"] = [int(item) for item in teammates_from_options]

    if action_type == "cupid":
        available = [int(item) for item in status.get("human_action_options", {}).get("candidates") or []]
        if len(available) >= 2:
            return {"pair": available[:2]}
        return {"pair": []}

    if action_type == "wild_child":
        available = [int(item) for item in status.get("human_action_options", {}).get("candidates") or []]
        return {"target": available[0] if available else None}

    if action_type == "speech":
        if role == "预言家":
            wolf_checks = [int(target) for target, result in known_results.items() if result == "狼人"]
            if wolf_checks:
                content = (
                    f"我是{seat}号，身份是预言家，昨晚我查了{wolf_checks[0]}号是狼人。"
                    " 这不是随便试探，我今天就会把票压在这个位置。"
                    " 小局容错很低，好人别把真查杀当成普通互踩。"
                )
                return {"content": content}
            good_checks = [int(target) for target, result in known_results.items() if result == "好人"]
            if good_checks:
                content = (
                    f"我是{seat}号，身份是预言家，昨晚我查了{good_checks[0]}号是好人。"
                    " 这轮我不接受无理由冲票，优先看谁在借节奏推人、谁在回避站边。"
                    " 如果后置位有人对跳或者逻辑明显变形，我会直接把票压过去。"
                )
                return {"content": content}
        if role == "女巫":
            content = (
                f"我是{seat}号，今天先按好人视角把话说直。"
                " 小局里最怕的不是没人说话，而是信息没铺开就先把一个人抬走。"
                " 我这轮更想看谁在硬带票、谁在回避关键身份线，别用一句状态像就定生死。"
            )
            return {"content": content}
        if role == "守卫":
            content = (
                f"我是{seat}号，我先给个保守但明确的立场。"
                " 现在信息不够的时候，别急着把唯一明跳神职或者首个压力位直接推出去。"
                " 今天谁的逻辑最不自洽、又最像借势跟票，我就会把压力给谁。"
            )
            return {"content": content}
        target = best_suspicion_target(exclude=teammates | {seat})
        if "狼" not in str(private_view.get("camp")):
            recent_speech_count = sum(1 for log in public_logs if log.get("type") == "speech" and log.get("day") == status.get("day_count"))
            if recent_speech_count == 0:
                memory["day_pressure_target"] = target
                content = (
                    f"我是{seat}号，我先给一个当前压力位：{target}号。"
                    " 这个位置不是我乱点的，我主要看谁先急着定人、谁只复读态度却不回应前置位的问题。"
                    " 后置位等会儿别只讲态度，直接说你更怀疑谁、为什么；"
                    " 如果没有更硬的新信息，我今天会优先在这个方向出票。"
                )
                return {"content": content}
        if "狼" in str(private_view.get("camp")):
            memory["day_pressure_target"] = target
            content = (
                f"我是{seat}号，我先不把话说满。"
                f" 现在我会优先追问{target}号，但还不到直接拍死的程度。"
                " 小局最怕有人先抢节奏再逼全场跟票，所以我更看重后置位能不能把怀疑链讲具体。"
                " 如果后面没有新增信息，我会在这个压力位附近出票，但今天不接受纯情绪冲票。"
            )
        else:
            content = (
                f"我是{seat}号，今天我先给一个明确压力位：{target}号。"
                " 现在信息还不算满，但这个位置的发言最需要继续追问。"
                " 如果后面没有更强反证，我会把票挂在这里。"
            )
        return {"content": content}

    if action_type == "vote":
        if "狼" in str(private_view.get("camp")):
            target = best_non_teammate(exclude={seat}) or best_suspicion_target(exclude=teammates | {seat})
        else:
            preferred = memory.get("day_pressure_target")
            scores = score_candidates()
            protected = {
                candidate for candidate, score in scores.items()
                if score <= -8
            }
            if preferred in candidates and preferred not in protected and scores.get(preferred, 0) >= 1:
                target = preferred
            else:
                viable = [candidate for candidate in candidates if candidate not in protected]
                if viable:
                    target = max(viable, key=lambda item: (scores.get(item, 0), -item))
                else:
                    target = best_suspicion_target(exclude={seat})
        return {"target": target}

    if action_type == "wolf":
        scores = score_candidates()
        target = max(
            [candidate for candidate in candidates if candidate not in teammates and candidate != seat],
            key=lambda item: (scores.get(item, 0), -item),
            default=None,
        )
        return {"target": target}

    if action_type == "guard":
        last_target = private_view.get("guard_last_target") or memory.get("last_guard_target")
        ordered = sorted(alive_seats, key=lambda item: (score_candidates().get(item, 0), -item))
        target = next((item for item in ordered if item != seat and item != int(last_target or 0)), None)
        memory["last_guard_target"] = target
        return {"target": target}

    if action_type == "seer":
        checked = {int(key) for key in known_results.keys()}
        target = best_suspicion_target(exclude=checked | {seat})
        if target is None:
            target = next((candidate for candidate in candidates if candidate not in checked and candidate != seat), None)
        return {"target": target}

    if action_type == "witch_heal":
        victim = status.get("human_action_options", {}).get("victim")
        use_heal = bool(victim) and (status.get("night_count", 0) <= 1 or int(victim) == seat)
        return {"use_heal": use_heal}

    if action_type == "witch_poison":
        scores = score_candidates()
        target = best_suspicion_target(exclude={seat})
        if target is None or scores.get(target, 0) < 2:
            return {"target": None}
        return {"target": target}

    if action_type == "hunter":
        target = best_suspicion_target(exclude={seat})
        return {"target": target}

    return {}


def extract_timeline(public_logs: list[dict[str, Any]]) -> list[str]:
    important = []
    for log in public_logs:
        if log.get("type") in {"phase", "death", "eliminate", "end", "reveal"}:
            important.append(log.get("content", ""))
    return important


def summarize_private_action(log: dict[str, Any], human_player: dict[str, Any]) -> Optional[str]:
    log_type = str(log.get("type") or "")
    meta = log.get("meta") or {}
    seat = int(log.get("seat") or 0)
    if not seat:
        return None

    if log_type == "guard_action":
        target = meta.get("target")
        return f"守卫行动：我夜里守了{target}号" if target else "守卫行动：我夜里选择空守"
    if log_type == "seer_action":
        target = meta.get("target")
        result = meta.get("result")
        if target and result:
            return f"预言家行动：我查验了{target}号，结果是{result}"
        return None
    if log_type == "witch_action":
        action = meta.get("action")
        target = meta.get("target")
        if action == "heal":
            return f"女巫行动：我选择救{target}号" if target else "女巫行动：我使用了解药"
        if action == "skip_heal":
            return "女巫行动：我选择不救人"
        if action == "poison":
            return f"女巫行动：我毒了{target}号" if target else "女巫行动：我使用了毒药"
        if action == "skip_poison":
            return "女巫行动：我选择不下毒"
        return None
    if log_type == "wolf_action" and "狼" in str(human_player.get("camp", "")):
        target = meta.get("target")
        return f"狼人行动：我参与决定夜刀{target}号" if target else "狼人行动：我参与了夜间刀口决策"
    return None


def summarize_human_role_event(log: dict[str, Any], human_seat: int) -> Optional[str]:
    log_type = str(log.get("type") or "")
    meta = log.get("meta") or {}
    seat = int(meta.get("seat") or log.get("seat") or 0)
    if seat != human_seat:
        return None

    content = str(log.get("content") or "")
    if log_type == "wild_child_awaken":
        idol = meta.get("idol")
        return f"角色事件：我的榜样{idol}号死亡后，我已转入狼人阵营" if idol else "角色事件：我的榜样死亡后，我已转入狼人阵营"
    if log_type == "cupid_action":
        pair = meta.get("pair") or []
        if isinstance(pair, list) and len(pair) == 2:
            return f"角色事件：我在首夜连接了{pair[0]}号与{pair[1]}号成为情侣"
        return "角色事件：我在首夜完成了情侣连线"
    if log_type == "system" and "秘密转入狼人阵营" in content:
        return "角色事件：我在被狼人袭击后秘密转入了狼人阵营"
    if log_type == "system" and "受祝福者抵挡了第一次狼人袭击" in content:
        return "角色事件：我抵挡了第一次狼人袭击"
    if log_type == "reveal" and "翻牌为白痴" in content:
        return "角色事件：我被票出时翻牌为白痴，保住性命但失去了投票权"
    return None


def review_game(
    scenario: dict[str, Any],
    game_id: str,
    players: list[dict[str, Any]],
    public_logs: list[dict[str, Any]],
    private_logs: list[dict[str, Any]],
    human_seat: int,
    report_dir: Path,
) -> dict[str, Any]:
    human_player = next(player for player in players if int(player["seat"]) == human_seat)
    human_role = str(human_player.get("role") or "")
    human_camp = str(human_player.get("camp") or "")
    winner = next((log.get("content") for log in public_logs if log.get("type") == "end"), "未知")
    timeline = extract_timeline(public_logs)
    llm_traces = [log for log in private_logs if log.get("type") == "llm_trace"]
    cached_tokens = sum(int((log.get("meta") or {}).get("cached_tokens") or 0) for log in llm_traces)
    speeches = [log for log in public_logs if log.get("type") == "speech"]
    votes = [log for log in public_logs if log.get("type") == "vote" and "投给了" in str(log.get("content"))]
    peaceful_nights = sum(1 for log in public_logs if "平安夜" in str(log.get("content")))
    death_logs = [log for log in public_logs if log.get("type") == "death"]
    human_public_actions = [log for log in public_logs if int(log.get("seat") or 0) == human_seat and log.get("type") in {"speech", "vote", "hunter"}]
    human_private_actions: list[str] = []
    human_role_events: list[str] = []
    for log in private_logs:
        if int(log.get("seat") or 0) == human_seat and log.get("type") in {"guard_action", "seer_action", "witch_action"}:
            summary = summarize_private_action(log, human_player)
            if summary:
                human_private_actions.append(summary)
        elif "狼" in str(human_player.get("camp")) and log.get("type") == "wolf_action":
            summary = summarize_private_action(log, human_player)
            if summary:
                human_private_actions.append(summary)
        role_event = summarize_human_role_event(log, human_seat)
        if role_event and role_event not in human_role_events:
            human_role_events.append(role_event)

    private_role_logs = [log for log in private_logs if int(log.get("seat") or 0) == human_seat]
    wild_child_turned = any(log.get("type") == "wild_child_awaken" for log in private_role_logs)
    cursed_turned = any(
        log.get("type") == "system"
        and not log.get("is_public", True)
        and "秘密转入狼人阵营" in str(log.get("content") or "")
        for log in private_role_logs
    )

    identity_summary = f"{human_role} / {human_camp}"
    if human_role == "野孩子" and wild_child_turned:
        identity_summary = f"{human_role} / 初始好人阵营，局内已转为狼人阵营"
    elif human_role == "被诅咒者" and cursed_turned:
        identity_summary = f"{human_role} / 初始好人阵营，局内已转为狼人阵营"

    if "狼" in human_camp:
        agency_note = "我这局站在狼队视角，能主动操控夜刀和白天带节奏，参与感最强。"
    else:
        agency_note = "我这局站在好人视角，行动更依赖信息增长，最关键的是白天点狼和夜间技能收益。"

    ux_notes = []
    if len(speeches) > scenario["total_players"] * 2:
        ux_notes.append("发言量充足，但长段发言连续出现时，用户阅读负担偏重，前端应考虑折叠和重点高亮。")
    else:
        ux_notes.append("发言长度总体可读，但仍建议把“身份声明、结论、投票对象”拆成结构化展示。")
    if peaceful_nights:
        ux_notes.append("平安夜会明显拉高悬念，值得在前端强化夜晚结算动画和原因提示。")
    if cached_tokens == 0:
        ux_notes.append("这局日志里缓存 token 仍为 0，说明实战 prompt 还不够长且不够稳定，成本优化空间仍然很大。")
    else:
        ux_notes.append(f"这局出现了 {cached_tokens} 个 cached tokens，说明缓存策略已开始产生实战收益。")

    balance_notes = []
    wolf_count = sum(1 for player in players if "狼" in player.get("camp", ""))
    if "狼人阵营" in winner and len(death_logs) <= 2:
        balance_notes.append("狼人赢得偏快，说明当前配置下夜刀收益过高，白天容错偏低。")
    elif "好人阵营" in winner and peaceful_nights:
        balance_notes.append("好人能靠平安夜把节奏拖回来，守卫/女巫在这个配置下有明显存在感。")
    else:
        balance_notes.append("胜负节奏相对自然，但是否平衡仍需要拉到 10 局总样本再判断。")
    if wolf_count >= 3:
        balance_notes.append("三狼局对白天票型的压迫更强，若继续扩充人数，建议同步加神职或减少强势狼人对白天的滚雪球。")
    elif wolf_count == 2:
        balance_notes.append("双狼局更考验白天发言质量，如果人类玩家体验偏弱，可以考虑给好人更明确的公开信息反馈。")
    else:
        balance_notes.append("单狼局更吃白天公投准确率；如果真查杀或单跳关键身份仍频繁被误票，说明白天信息利用还要继续补强。")

    report_path = report_dir / f"{scenario['name']}_{game_id}.md"
    content = "\n".join(
        [
            f"# {scenario['name']} / {game_id}",
            "",
            "## 配置",
            f"- 玩家数：{scenario['total_players']}",
            f"- 狼人数：{scenario['num_wolves']}",
            f"- 角色配置：`{json.dumps(scenario['role_config'], ensure_ascii=False)}`",
            f"- 我的人类座位：{human_seat} 号",
            f"- 我的真实身份：{identity_summary}",
            "",
            "## 结果",
            f"- 胜负：{winner}",
            f"- 我的存活状态：{'存活' if human_player.get('alive') else '阵亡'}",
            f"- 公开发言条数：{len(speeches)}",
            f"- 投票日志条数：{len(votes)}",
            f"- LLM 请求数：{len(llm_traces)}",
            f"- 缓存命中 token：{cached_tokens}",
            "",
            "## 我这局的体感",
            agency_note,
            "",
            "## 我这个玩家的实际动作",
            *[f"- {log.get('type')}: {log.get('content')}" for log in human_public_actions[:6]],
            *[f"- {item}" for item in human_private_actions[:6]],
            *[f"- {item}" for item in human_role_events[:6]],
            "",
            "## 关键时间线",
            *[f"- {item}" for item in timeline],
            "",
            "## 用户体验观察",
            *[f"- {item}" for item in ux_notes],
            "",
            "## 阵营平衡观察",
            *[f"- {item}" for item in balance_notes],
            "",
        ]
    )
    report_path.write_text(content + "\n", encoding="utf-8")
    return {
        "game_id": game_id,
        "scenario": scenario["name"],
        "winner": winner,
        "human_role": human_player.get("role"),
        "human_camp": human_player.get("camp"),
        "human_alive": human_player.get("alive"),
        "cached_tokens": cached_tokens,
        "report_path": str(report_path),
    }


def run_scenario(client: httpx.Client, scenario: dict[str, Any], index: int, report_dir: Path) -> dict[str, Any]:
    human_seat = 1
    memory: dict[str, Any] = {}
    started_at = time.time()
    payload = {
        "human_seats": [human_seat],
        "total_players": scenario["total_players"],
        "num_wolves": scenario["num_wolves"],
        "role_config": scenario["role_config"],
        "random_models": False,
        "seat_model_map": build_seat_model_map(scenario["total_players"], index),
        "god_mode": {"enabled": True, "password": GOD_PASSWORD},
    }
    created = fetch_json(client, "POST", "/api/game/create", json=payload)
    game_id = created["game_id"]
    fetch_json(client, "POST", f"/api/game/{game_id}/start")

    while True:
        if time.time() - started_at > SCENARIO_TIMEOUT_SECONDS:
            raise TimeoutError(f"场景在 {SCENARIO_TIMEOUT_SECONDS} 秒后超时：{scenario['name']} / {game_id}")
        status = fetch_json(client, "GET", f"/api/game/{game_id}/status")
        if status.get("phase") == "ended":
            break
        if int(status.get("waiting_for_human") or 0) == human_seat:
            private_view = fetch_json(client, "GET", f"/api/game/{game_id}/player/{human_seat}")
            public_payload = fetch_json(client, "GET", f"/api/game/{game_id}/log?limit=500")
            action = infer_human_action(
                str(status.get("human_action_type")),
                private_view,
                public_payload.get("logs", []),
                status,
                memory,
            )
            fetch_json(
                client,
                "POST",
                f"/api/game/{game_id}/action",
                json={"action_type": status.get("human_action_type"), "data": action},
            )
            time.sleep(0.2)
            continue
        time.sleep(1.0)

    game_detail = fetch_json(client, "GET", f"/api/stats/game/{game_id}")
    god_logs = fetch_json(client, "GET", f"/api/game/{game_id}/god-mode/logs?password={GOD_PASSWORD}&limit=1000")
    return review_game(
        scenario=scenario,
        game_id=game_id,
        players=game_detail["players"],
        public_logs=game_detail.get("public_logs") or game_detail.get("logs") or [],
        private_logs=game_detail.get("private_logs") or god_logs.get("logs") or [],
        human_seat=human_seat,
        report_dir=report_dir,
    )


def run_scenario_with_recovery(
    process: Optional[subprocess.Popen[str]],
    client: httpx.Client,
    scenario: dict[str, Any],
    index: int,
    report_dir: Path,
) -> tuple[dict[str, Any], Optional[subprocess.Popen[str]], httpx.Client]:
    last_error: Optional[Exception] = None
    for attempt in range(SERVER_RECOVERY_RETRIES + 1):
        try:
            result = run_scenario(client, scenario, index, report_dir)
            return result, process, client
        except Exception as exc:
            last_error = exc
            if attempt >= SERVER_RECOVERY_RETRIES or not is_recoverable_server_error(exc):
                break
            print(
                json.dumps(
                    {
                        "scenario": scenario["name"],
                        "event": "server_recovery",
                        "attempt": attempt + 1,
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            process, client = restart_server(process, client)
    assert last_error is not None
    raise last_error


def write_summary(report_dir: Path, results: list[dict[str, Any]]) -> None:
    winners = Counter("狼人阵营" if "狼人阵营" in item["winner"] else "好人阵营" for item in results)
    human_roles = Counter(item["human_role"] for item in results)
    alive_rate = sum(1 for item in results if item["human_alive"]) / len(results)
    cached_total = sum(int(item["cached_tokens"]) for item in results)
    wolf_wins = winners.get("狼人阵营", 0)
    good_wins = winners.get("好人阵营", 0)
    total_games = len(results)

    lines = [
        "# 批量复盘总览",
        "",
        f"- 总对局数：{total_games}",
        f"- 狼人胜场：{wolf_wins}",
        f"- 好人胜场：{good_wins}",
        f"- 我的人类席位存活率：{alive_rate:.2%}",
        f"- 批量实战累计缓存 token：{cached_total}",
        f"- 我扮演过的身份分布：`{json.dumps(dict(human_roles), ensure_ascii=False)}`",
        "",
        "## 总体判断",
    ]

    if total_games and wolf_wins == total_games:
        lines.append("- 这批样本是狼人全胜，已经属于明显单边碾压，当前配置或决策逻辑需要继续纠偏。")
    elif total_games and good_wins == total_games:
        lines.append("- 这批样本是好人全胜，已经属于明显单边碾压，当前配置或决策逻辑需要继续纠偏。")
    elif wolf_wins >= max(3, total_games - 1):
        lines.append("- 狼人明显占优，尤其在小样本里也持续拿到多数胜场，说明当前局面仍偏狼。")
    elif good_wins >= max(3, total_games - 1):
        lines.append("- 好人明显占优，尤其在小样本里也持续拿到多数胜场，说明当前局面偏好人。")
    elif winners.get("狼人阵营", 0) >= 7:
        lines.append("- 狼人整体偏强，尤其是 5-7 人小局里，夜刀滚雪球过快。")
    elif winners.get("好人阵营", 0) >= 7:
        lines.append("- 好人整体偏强，神职链条在当前规则里给了足够高的信息和容错。")
    else:
        lines.append(f"- {total_games} 局结果没有明显单边碾压，但不同人数下波动仍然很大。")

    lines.extend(
        [
            "- 体验层面最该补的是结构化日志阅读：把发言结论、投票对象、夜间结算原因分开展示，用户会更容易跟上节奏。",
            "- 成本层面最该补的是长前缀缓存策略：当前实战里多半还没吃到缓存红利，建议把稳定规则前缀和历史摘要固化到更长、更稳定的 instructions 段。",
            "- 平衡层面最值得继续试的是按人数切模板：5-6 人局需要非常谨慎地控狼人数；在当前胜负判定下，8-9 人局继续维持 2 狼会更稳，除非同步重做夜间信息量和胜利阈值。",
            "",
            "## 单局复盘",
        ]
    )
    for item in results:
        lines.append(f"- [{item['scenario']} / {item['game_id']}]({Path(item['report_path']).name})")

    (report_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    process, client = ensure_server()
    results: list[dict[str, Any]] = []
    try:
        for index, scenario in enumerate(SCENARIOS):
            try:
                result, process, client = run_scenario_with_recovery(process, client, scenario, index, REPORT_ROOT)
            except Exception as exc:
                result = {
                    "game_id": "unknown",
                    "scenario": scenario["name"],
                    "winner": f"失败: {exc}",
                    "human_role": "未知",
                    "human_camp": "未知",
                    "human_alive": False,
                    "cached_tokens": 0,
                    "report_path": "",
                    "error": str(exc),
                }
            results.append(result)
            print(json.dumps(result, ensure_ascii=False))
        write_summary(REPORT_ROOT, results)
        print(f"报告已写入：{REPORT_ROOT}")
        return 0
    finally:
        client.close()
        stop_server(process)


if __name__ == "__main__":
    raise SystemExit(main())
