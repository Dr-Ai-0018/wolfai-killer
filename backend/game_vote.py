"""
白天投票阶段辅助逻辑。
"""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class VoteRoundResolution:
    """投票计票后的结果摘要。"""

    vote_counts: Dict[int, int]
    max_votes: int
    top_targets: List[int]

    @property
    def is_tie(self) -> bool:
        return len(self.top_targets) > 1

    @property
    def eliminated_seat(self) -> Optional[int]:
        if self.is_tie:
            return None
        return self.top_targets[0]


def apply_vote_rights(players: Dict[int, Any], alive_seats: Iterable[int], restricted_voters: Optional[set[int]]) -> set[int]:
    """应用替罪羊留下的下一轮投票权限制，并返回当前生效的限制集合。"""
    active_restriction = set(restricted_voters or set())
    for seat in alive_seats:
        players[seat].can_vote = not active_restriction or seat in active_restriction
    return active_restriction


def count_votes(votes: Dict[int, int]) -> Dict[int, int]:
    """将 voter -> target 映射转换为 target -> count 计票结果。"""
    vote_counts: Dict[int, int] = {}
    for target in votes.values():
        vote_counts[target] = vote_counts.get(target, 0) + 1
    return vote_counts


def resolve_vote_round(votes: Dict[int, int]) -> Optional[VoteRoundResolution]:
    """解析本轮投票是否出局或平票。"""
    vote_counts = count_votes(votes)
    if not vote_counts:
        return None

    max_votes = max(vote_counts.values())
    top_targets = [seat for seat, count in vote_counts.items() if count == max_votes]
    return VoteRoundResolution(
        vote_counts=vote_counts,
        max_votes=max_votes,
        top_targets=top_targets,
    )


def build_vote_eliminate_log(resolution: VoteRoundResolution, eliminated_chain: List[int]) -> Dict[str, Any]:
    """构建正常公投出局日志。"""
    eliminated = resolution.eliminated_seat
    assert eliminated is not None
    return {
        "type": "eliminate",
        "content": f"{eliminated}号被投票出局（{resolution.max_votes}票）",
        "meta": {
            "eliminated": eliminated,
            "votes": resolution.max_votes,
            "vote_counts": resolution.vote_counts,
            "chain": eliminated_chain,
        },
    }


def build_vote_result_log(resolution: VoteRoundResolution) -> Dict[str, Any]:
    """构建获得最高票但未实际死亡的日志。"""
    eliminated = resolution.eliminated_seat
    assert eliminated is not None
    return {
        "type": "vote_result",
        "content": f"{eliminated}号获得最多票（{resolution.max_votes}票），但未实际出局。",
        "meta": {
            "seat": eliminated,
            "votes": resolution.max_votes,
            "vote_counts": resolution.vote_counts,
            "eliminated": False,
        },
    }


def build_scapegoat_tie_log(
    resolution: VoteRoundResolution,
    scapegoat_seat: int,
    eliminated_chain: List[int],
) -> Dict[str, Any]:
    """构建替罪羊平票替死日志。"""
    return {
        "type": "eliminate",
        "content": f"平票后，{scapegoat_seat}号替罪羊替死出局。",
        "meta": {
            "eliminated": scapegoat_seat,
            "tie_targets": resolution.top_targets,
            "vote_counts": resolution.vote_counts,
            "chain": eliminated_chain,
        },
    }


def build_vote_tie_log(resolution: VoteRoundResolution) -> Dict[str, Any]:
    """构建平票无人出局日志。"""
    return {
        "type": "vote",
        "content": "平票，无人出局",
        "meta": {
            "vote_counts": resolution.vote_counts,
            "tie_targets": resolution.top_targets,
        },
    }
