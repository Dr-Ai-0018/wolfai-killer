"""
Game state models
"""
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


class GamePhase(Enum):
    """Game phases"""
    WAITING = "waiting"
    NIGHT = "night"
    DAY = "day"
    VOTE = "vote"
    ENDED = "ended"


@dataclass
class VoteRecord:
    """Record of a single vote"""
    voter: int
    target: int
    round: int


@dataclass
class PhantomAction:
    """Record of a dead player's phantom action (for afterlife review)"""
    night: int
    role: str
    seat: int
    action_type: str
    target: Optional[int]
    decision: Optional[str]
    timestamp: str


@dataclass
class GameState:
    """Serializable game state for frontend"""
    game_id: str
    phase: str
    day_count: int
    night_count: int
    paused: bool
    winner: Optional[str]
    alive_seats: List[int]
    waiting_for_human: Optional[int]
    human_action_type: Optional[str]
    human_action_options: Dict[str, Any]
    current_action_role: Optional[str]
    current_action_message: Optional[str]
    # Vote visualization
    current_votes: Dict[int, int] = field(default_factory=dict)
    vote_counts: Dict[int, int] = field(default_factory=dict)
