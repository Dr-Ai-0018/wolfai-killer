"""
游戏结束与统计构建辅助
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple


def build_end_game_logs(players: Dict[int, Any], winner: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    end_log = {
        "type": "end",
        "content": f"游戏结束！{winner}获胜！",
    }
    roles_info = [f"{seat}号：{players[seat].role.value}" for seat in sorted(players.keys())]
    reveal_log = {
        "type": "reveal",
        "content": "身份揭晓：" + "，".join(roles_info),
    }
    return end_log, reveal_log


def build_players_info(players: Dict[int, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "seat": seat,
            "role": player.role.value,
            "camp": player.camp.value,
            "is_human": player.is_human,
            "alive": player.alive,
            "model_name": player.model_name,
            "personality_name": player.personality.name if player.personality else None,
        }
        for seat, player in players.items()
    ]


def split_logs_by_visibility(logs: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    public_logs: List[Dict[str, Any]] = []
    private_logs: List[Dict[str, Any]] = []
    for log in logs:
        if log.get("is_public", True):
            public_logs.append(log)
        else:
            private_logs.append(log)
    return public_logs, private_logs


def count_logs_by_type(logs: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for log in logs:
        log_type = str(log.get("type") or "unknown")
        counts[log_type] = counts.get(log_type, 0) + 1
    return counts


def summarize_llm_usage(logs: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    llm_traces = [log for log in logs if log.get("type") == "llm_trace"]
    return {
        "request_count": len(llm_traces),
        "input_tokens": sum(int((log.get("meta") or {}).get("input_tokens") or 0) for log in llm_traces),
        "cached_tokens": sum(int((log.get("meta") or {}).get("cached_tokens") or 0) for log in llm_traces),
        "output_tokens": sum(int((log.get("meta") or {}).get("output_tokens") or 0) for log in llm_traces),
    }


def build_game_record(
    *,
    game_id: str,
    start_time: Optional[datetime],
    end_time: datetime,
    players: Dict[int, Any],
    winner: str,
    day_count: int,
    logs: List[Dict[str, Any]],
    day_summary: Dict[str, Any],
    phantom_actions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    duration = 0
    if start_time:
        duration = int((end_time - start_time).total_seconds())

    players_info = build_players_info(players)
    public_logs, private_logs = split_logs_by_visibility(logs)

    return {
        "game_id": game_id,
        "start_time": start_time.isoformat() if start_time else None,
        "end_time": end_time.isoformat(),
        "duration": duration,
        "total_players": len(players),
        "num_wolves": len([player for player in players.values() if player.camp.value == "狼人阵营"]),
        "num_humans": len([player for player in players.values() if player.is_human]),
        "winner_camp": winner,
        "total_rounds": day_count,
        "players": players_info,
        "logs": public_logs,
        "public_logs": public_logs,
        "private_logs": private_logs,
        "day_summary": day_summary,
        "log_counts": count_logs_by_type(logs),
        "llm_usage_summary": summarize_llm_usage(private_logs),
        "phantom_actions": list(phantom_actions),
    }
