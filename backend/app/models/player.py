"""
Player and Role models
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Optional, Any


class Role(Enum):
    """Player roles"""
    WOLF = "狼人"
    VILLAGER = "村民"
    SEER = "预言家"
    WITCH = "女巫"
    HUNTER = "猎人"
    GUARD = "守卫"


class Camp(Enum):
    """Player camps/factions"""
    WOLF = "狼人阵营"
    GOOD = "好人阵营"


@dataclass
class Personality:
    """AI personality configuration"""
    code: str
    name: str
    description: str
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "code": self.code,
            "name": self.name,
            "description": self.description,
        }


# Default personalities
DEFAULT_PERSONALITIES = [
    Personality("leader_bold", "勇敢领袖型", "敢于发言、敢带节奏、愿意拍板做决定"),
    Personality("careful_timid", "胆小细腻型", "谨慎、怕背锅，喜欢观望和跟票"),
    Personality("aggressive", "激进冲锋型", "喜欢强势发言和发起冲票"),
    Personality("schemer", "老谋深算型", "重视长期收益，会刻意隐藏真实想法"),
    Personality("buddha", "佛系摆烂型", "偏随缘，不太愿意深度推理"),
    Personality("rational_analyst", "理性分析型", "偏好列举信息、分析票型和概率"),
    Personality("suspicious", "疑心病重型", "对多数人都保持怀疑"),
    Personality("team_player", "团结协作型", "更愿意跟随自己信任的队友"),
    Personality("emotional", "情绪化型", "容易被场上氛围影响，发言带感情色彩"),
    Personality("contrarian", "唱反调型", "喜欢提出与主流不同的观点"),
    Personality("quiet_observer", "沉默观察型", "话少但关键时刻会发表重要意见"),
    Personality("chameleon", "变色龙型", "善于根据局势改变立场和发言风格"),
]


@dataclass
class Player:
    """Player in the game"""
    seat: int
    role: Role
    camp: Camp
    personality: Personality
    model_name: str = ""
    is_human: bool = False
    alive: bool = True
    avatar: str = ""
    
    # Role-specific state
    seer_results: Dict[int, str] = field(default_factory=dict)
    has_heal: bool = True
    has_poison: bool = True
    guard_last_target: Optional[int] = None
    
    def to_public_dict(self) -> Dict[str, Any]:
        """Public info visible to all players"""
        return {
            "seat": self.seat,
            "alive": self.alive,
            "is_human": self.is_human,
            "avatar": self.avatar,
        }
    
    def to_private_dict(self) -> Dict[str, Any]:
        """Private info for the player or god mode"""
        return {
            **self.to_public_dict(),
            "role": self.role.value,
            "camp": self.camp.value,
            "personality": self.personality.to_dict() if self.personality else None,
            "model_name": self.model_name,
            "seer_results": self.seer_results,
            "has_heal": self.has_heal,
            "has_poison": self.has_poison,
        }
