"""
Game review and public-signal summarization helpers.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


ROLE_CLAIM_KEYWORDS = {
    "预言家": ["预言家"],
    "女巫": ["女巫"],
    "守卫": ["守卫"],
    "猎人": ["猎人"],
    "狐狸": ["狐狸"],
    "天使": ["天使"],
    "替罪羊": ["替罪羊"],
    "共济会": ["共济会", "共济会成员"],
    "圣徒": ["圣徒"],
    "丘比特": ["丘比特"],
    "长老": ["长老", "高级村民"],
    "白痴": ["白痴"],
    "野孩子": ["野孩子"],
    "被诅咒者": ["被诅咒者"],
    "受祝福者": ["受祝福者"],
}


def extract_speech_meta(
    speech: str,
    role_claim_keywords: Dict[str, List[str]] | None = None,
) -> Dict[str, Any]:
    """Pull lightweight structure from free-form speech for UI and heuristics."""
    keywords_map = role_claim_keywords or ROLE_CLAIM_KEYWORDS
    mentioned_seats = sorted({int(item) for item in re.findall(r"(\d+)号", speech)})
    claimed_role = None
    claim_window = re.split(r"[。；\n]", speech, maxsplit=1)[0][:120].strip()
    for role_name, keywords in keywords_map.items():
        for keyword in keywords:
            claim_patterns = [
                rf"^[【\[]?\s*我是\d+号(?:玩家)?[】\]]?.*?身份是{keyword}",
                rf"^[【\[]?\s*我是\d+号(?:玩家)?[】\]]?.*?我是{keyword}",
                rf"^[【\[]?\s*我是\d+号(?:玩家)?[】\]]?.*?跳{keyword}",
                rf"^[【\[]?\s*我是\d+号(?:玩家)?[】\]]?.*?单跳{keyword}",
            ]
            if any(re.search(pattern, claim_window) for pattern in claim_patterns):
                claimed_role = role_name
                break
        if claimed_role:
            break
    return {
        "claimed_role": claimed_role,
        "mentioned_seats": mentioned_seats,
    }


def build_public_claim_summary(logs: Iterable[Dict[str, Any]], alive_seats: Iterable[int]) -> Dict[str, List[int]]:
    """Summarize public role claims from alive players."""
    claims: Dict[str, List[int]] = {}
    alive = {int(seat) for seat in alive_seats}
    for log in logs:
        if not log.get("is_public") or log.get("type") != "speech":
            continue
        seat = int(log.get("seat") or 0)
        if seat not in alive:
            continue
        claimed_role = (log.get("meta") or {}).get("claimed_role")
        if claimed_role:
            claims.setdefault(str(claimed_role), [])
            if seat not in claims[str(claimed_role)]:
                claims[str(claimed_role)].append(seat)
    return claims


def build_day_summary(
    logs: Iterable[Dict[str, Any]],
    alive_seats: Iterable[int],
    day_count: int,
    phase: str,
) -> Dict[str, Any]:
    """Summarize public day-phase signals for UI consumption."""
    claims = build_public_claim_summary(logs, alive_seats)
    speeches = [
        log for log in logs
        if log.get("is_public") and log.get("type") == "speech" and log.get("day") == day_count
    ]
    votes = [
        log for log in logs
        if log.get("is_public") and log.get("type") == "vote" and log.get("day") == day_count
    ]
    vote_counts: Dict[int, int] = {}
    vote_map: Dict[int, int] = {}
    mentioned_pressure: Dict[int, int] = {}
    for log in speeches:
        meta = log.get("meta") or {}
        for seat in meta.get("mentioned_seats") or []:
            seat_num = int(seat)
            mentioned_pressure[seat_num] = mentioned_pressure.get(seat_num, 0) + 1
    for log in votes:
        meta = log.get("meta") or {}
        voter = int(meta.get("voter") or 0)
        target = int(meta.get("target") or 0)
        if voter and target:
            vote_map[voter] = target
            vote_counts[target] = vote_counts.get(target, 0) + 1

    pressure_board = []
    alive = {int(seat) for seat in alive_seats}
    for seat in sorted(alive):
        pressure_board.append({
            "seat": seat,
            "mentions": mentioned_pressure.get(seat, 0),
            "votes": vote_counts.get(seat, 0),
            "claimed_role": next((role_name for role_name, seats in claims.items() if seat in seats), None),
        })
    pressure_board.sort(key=lambda item: (-item["votes"], -item["mentions"], item["seat"]))

    return {
        "day": day_count,
        "phase": phase,
        "claims": claims,
        "vote_map": vote_map,
        "vote_counts": vote_counts,
        "pressure_board": pressure_board,
    }
