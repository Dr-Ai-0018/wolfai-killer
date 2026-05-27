"""
Catalog of roles, camps, personalities, and static game configuration helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


def normalize_model_ids(raw_models: Any) -> List[str]:
    """Normalize config models into a unique list of ids."""
    if not isinstance(raw_models, list):
        return []

    model_ids: List[str] = []
    for item in raw_models:
        model_id = ""
        if isinstance(item, str):
            model_id = item.strip()
        elif isinstance(item, dict):
            candidate = item.get("id") or item.get("name") or item.get("model") or item.get("value")
            if isinstance(candidate, str):
                model_id = candidate.strip()

        if model_id and model_id not in model_ids:
            model_ids.append(model_id)

    return model_ids


class Role(Enum):
    VILLAGER = "村民"
    WOLF = "狼人"
    SEER = "预言家"
    WITCH = "女巫"
    HUNTER = "猎人"
    GUARD = "守卫"
    FOX = "狐狸"
    ANGEL = "天使"
    SCAPEGOAT = "替罪羊"
    MASON = "共济会"
    SUPER_SAINT = "圣徒"
    CUPID = "丘比特"
    IDIOT = "白痴"
    ELDER = "长老"
    WILD_CHILD = "野孩子"
    CURSED = "被诅咒者"
    BLESSED = "受祝福者"
    WOLF_KING = "狼王"
    WHITE_WOLF = "白狼王"
    BEAUTY = "狼美人"


class Camp(Enum):
    GOOD = "好人阵营"
    WOLF = "狼人阵营"


@dataclass
class Personality:
    code: str
    name: str
    description: str


PERSONALITIES = [
    Personality("leader_bold", "勇敢领袖型", "敢于发言、敢带节奏、愿意拍板做决定，偏乐观，愿意承担风险，但不会无脑送死。"),
    Personality("careful_timid", "胆小细腻型", "谨慎、怕背锅，喜欢观望和跟票，很少主动带节奏，但思考细致。"),
    Personality("aggressive", "激进冲锋型", "喜欢强势发言和发起冲票，对怀疑对象会反复进攻，容忍一定误伤。"),
    Personality("schemer", "老谋深算型", "重视长期收益，会刻意隐藏真实想法，偶尔说反话迷惑别人。"),
    Personality("buddha", "佛系摆烂型", "偏随缘，不太愿意深度推理，但会遵守基本阵营利益，不会故意自爆。"),
    Personality("rational_analyst", "理性分析型", "像理工男/女，偏好列举信息、分析票型和概率，尽量减少感性判断。"),
    Personality("suspicious", "疑心病重型", "对多数人都保持怀疑，很容易起身对抗他人观点，但仍以本阵营获胜为目标。"),
    Personality("team_player", "团结协作型", "更愿意跟随自己信任的队友，不轻易起冲突，注重团队共识。"),
    Personality("showman", "表演欲强型", "发言风格夸张，有时会用戏剧化语言，但不胡乱自爆，仍会尽量让本阵营获胜。"),
    Personality("newbie_pure", "清澈无知萌新型", "对规则理解有限，容易犯错，但不会故意捣乱，会尝试照系统给的提示行事。"),
    Personality("trollish", "爱搞事阴阳人型", "喜欢质疑他人、抬杠和插科打诨，但不得故意自刀/自投，仍需遵守阵营利益。"),
    Personality("cold_programmer", "程序员理工型", "说话直白偏冷静，喜欢按'规则'和'最优解'思考，讨厌明显非理性行为。"),
]

PERSONALITY_MAP = {p.code: p for p in PERSONALITIES}
DEFAULT_MODEL_POOL = [
    "bl-DeepSeek-V3-250324",
    "bl-DeepSeek-V3.1-Terminus",
]
WOLF_ROLES = {Role.WOLF, Role.WOLF_KING, Role.WHITE_WOLF, Role.BEAUTY}
ROLE_CODE_MAP = {
    "WOLF": Role.WOLF,
    "VILLAGER": Role.VILLAGER,
    "SEER": Role.SEER,
    "WITCH": Role.WITCH,
    "HUNTER": Role.HUNTER,
    "GUARD": Role.GUARD,
    "FOX": Role.FOX,
    "ANGEL": Role.ANGEL,
    "SCAPEGOAT": Role.SCAPEGOAT,
    "MASON": Role.MASON,
    "SUPER_SAINT": Role.SUPER_SAINT,
    "CUPID": Role.CUPID,
    "IDIOT": Role.IDIOT,
    "ELDER": Role.ELDER,
    "WILD_CHILD": Role.WILD_CHILD,
    "CURSED": Role.CURSED,
    "BLESSED": Role.BLESSED,
    "WOLF_KING": Role.WOLF_KING,
    "WHITE_WOLF": Role.WHITE_WOLF,
    "BEAUTY": Role.BEAUTY,
}


def get_role_camp(role: Role) -> Camp:
    return Camp.WOLF if role in WOLF_ROLES else Camp.GOOD


def build_roles_from_config(
    total_players: int,
    num_wolves: int,
    role_config: Optional[Dict[str, int]] = None,
) -> List[Role]:
    if role_config:
        roles: List[Role] = []
        for role_code, count in role_config.items():
            if role_code in ROLE_CODE_MAP and count > 0:
                roles.extend([ROLE_CODE_MAP[role_code]] * count)
        while len(roles) < total_players:
            roles.append(Role.VILLAGER)
        return roles[:total_players]

    roles = [Role.WOLF] * num_wolves + [Role.SEER, Role.WITCH, Role.GUARD, Role.HUNTER, Role.FOX]
    while len(roles) < total_players:
        roles.append(Role.VILLAGER)
    return roles
