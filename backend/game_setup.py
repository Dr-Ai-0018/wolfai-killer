"""
对局初始化与玩家构建辅助逻辑。
"""

import random
from typing import Any, Dict, List, Optional

from game_catalog import Camp, PERSONALITIES, Role, build_roles_from_config, get_role_camp


def build_shuffled_roles(
    total_players: int,
    num_wolves: int,
    role_config: Optional[Dict[str, int]] = None,
) -> List[Role]:
    """构建并打乱本局角色列表。"""
    roles = build_roles_from_config(
        total_players=total_players,
        num_wolves=num_wolves,
        role_config=role_config,
    )
    random.shuffle(roles)
    return roles


def build_shuffled_avatars(avatars: Optional[List[str]]) -> List[str]:
    """返回打乱后的头像列表副本。"""
    if not avatars:
        return []

    shuffled = list(avatars)
    random.shuffle(shuffled)
    return shuffled


def resolve_ai_model_name(
    seat: int,
    models_pool: List[str],
    random_models: bool,
    seat_model_map: Optional[Dict[int, str]] = None,
) -> Optional[str]:
    """根据优先级为 AI 座位分配模型。"""
    if seat_model_map and seat in seat_model_map:
        return seat_model_map[seat]
    if random_models and models_pool:
        return random.choice(models_pool)
    if models_pool:
        return models_pool[0]
    return None


def build_player_specs(
    total_players: int,
    human_seats: List[int],
    num_wolves: int,
    models_pool: List[str],
    role_config: Optional[Dict[str, int]] = None,
    avatars: Optional[List[str]] = None,
    random_models: bool = True,
    seat_model_map: Optional[Dict[int, str]] = None,
) -> List[Dict[str, Any]]:
    """生成初始化玩家所需的规格数据。"""
    roles = build_shuffled_roles(
        total_players=total_players,
        num_wolves=num_wolves,
        role_config=role_config,
    )
    shuffled_avatars = build_shuffled_avatars(avatars)
    specs: List[Dict[str, Any]] = []

    for index, role in enumerate(roles):
        seat = index + 1
        is_human = seat in human_seats
        personality = None if is_human else random.choice(PERSONALITIES)
        specs.append(
            {
                "seat": seat,
                "role": role,
                "camp": get_role_camp(role),
                "is_human": is_human,
                "avatar": shuffled_avatars[index] if index < len(shuffled_avatars) else "1f642.webp",
                "model_name": None
                if is_human
                else resolve_ai_model_name(
                    seat=seat,
                    models_pool=models_pool,
                    random_models=random_models,
                    seat_model_map=seat_model_map,
                ),
                "personality": personality,
            }
        )

    return specs


def assign_mason_peers(players: Dict[int, Any]) -> None:
    """为共济会成员写入彼此可见的同伴座位号。"""
    mason_seats = [seat for seat, player in players.items() if getattr(player, "role", None) == Role.MASON]
    for seat in mason_seats:
        players[seat].mason_peers = [peer for peer in mason_seats if peer != seat]
