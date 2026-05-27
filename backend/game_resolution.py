"""
胜负判定与淘汰连锁规则辅助逻辑。
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from game_catalog import Camp, Role


@dataclass(frozen=True)
class EliminationRuleEffect:
    """淘汰前置规则的命中结果。"""

    kind: str
    seat: int
    cause: str
    role: str


def determine_winner(players: Dict[int, Any], angel_victory_seat: Optional[int]) -> Optional[str]:
    """根据当前存活状态判断胜利阵营。"""
    if angel_victory_seat is not None:
        return "天使阵营"

    alive_players = [player for player in players.values() if player.alive]
    if len(alive_players) == 2:
        first, second = alive_players
        if first.lover == second.seat and second.lover == first.seat and first.camp != second.camp:
            return "情侣阵营"

    wolves = [player for player in alive_players if player.camp == Camp.WOLF]
    goods = [player for player in alive_players if player.camp == Camp.GOOD]

    if not wolves:
        return "好人阵营"
    if len(wolves) >= len(goods):
        return "狼人阵营"
    return None


def should_disable_powers_for_elder(cause: str) -> bool:
    """长老以何种死因触发神职失效。"""
    return cause not in {"wolf_kill", "lover_suicide"}


def resolve_immediate_elimination_rule(player: Any, cause: str, day_count: int) -> Optional[EliminationRuleEffect]:
    """处理淘汰前立即生效的特殊规则。"""
    if player.role == Role.ANGEL and player.angel_active and cause in {"wolf_kill", "vote"} and day_count <= 1:
        player.alive = False
        player.angel_active = False
        return EliminationRuleEffect("angel_victory", player.seat, cause, player.role.value)

    if cause == "wolf_kill" and player.role == Role.ELDER and player.elder_lives > 1:
        player.elder_lives -= 1
        return EliminationRuleEffect("elder_survive", player.seat, cause, player.role.value)

    if cause == "wolf_kill" and player.role == Role.BLESSED and not player.blessing_used:
        player.blessing_used = True
        return EliminationRuleEffect("blessed_survive", player.seat, cause, player.role.value)

    if cause == "wolf_kill" and player.role == Role.CURSED and not player.cursed_turned:
        player.camp = Camp.WOLF
        player.cursed_turned = True
        return EliminationRuleEffect("cursed_turn", player.seat, cause, player.role.value)

    if cause == "vote" and player.role == Role.IDIOT and not player.idiot_revealed:
        player.idiot_revealed = True
        player.can_vote = False
        return EliminationRuleEffect("idiot_reveal", player.seat, cause, player.role.value)

    return None


def find_lover_chain_target(players: Dict[int, Any], seat: int) -> Optional[int]:
    """获取因情侣殉情需要连锁死亡的目标。"""
    player = players[seat]
    lover_seat = player.lover
    if not lover_seat:
        return None

    lover = players.get(lover_seat)
    if lover and lover.alive:
        return lover_seat
    return None


def awaken_wild_children(players: Dict[int, Any], dead_seat: int) -> List[int]:
    """榜样死亡后，将野孩子转入狼人阵营。"""
    awakened: List[int] = []
    for player in players.values():
        if (
            player.alive
            and player.role == Role.WILD_CHILD
            and not player.wild_child_awakened
            and player.idol == dead_seat
        ):
            player.camp = Camp.WOLF
            player.wild_child_awakened = True
            awakened.append(player.seat)
    return awakened
