"""
AI Werewolf Game Engine - Core game logic
Completely rewritten for WebSocket-first architecture
"""

import random
import json
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any, Set, Callable
from datetime import datetime
import httpx


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
    # 新增角色
    CUPID = "丘比特"
    IDIOT = "白痴"
    ELDER = "长老"
    WOLF_KING = "狼王"
    WHITE_WOLF = "白狼王"
    BEAUTY = "狼美人"


class Camp(Enum):
    GOOD = "好人阵营"
    WOLF = "狼人阵营"


class GamePhase(Enum):
    WAITING = "waiting"
    NIGHT = "night"
    DAY = "day"
    VOTE = "vote"
    ENDED = "ended"


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


@dataclass
class Player:
    seat: int
    role: Role
    camp: Camp
    is_human: bool
    model_name: Optional[str] = None
    personality: Optional[Personality] = None
    avatar: str = "1f642.webp"
    alive: bool = True
    has_heal: bool = True  # Witch
    has_poison: bool = True  # Witch
    seer_results: Dict[int, str] = field(default_factory=dict)
    guard_last_target: Optional[int] = None
    # 新角色属性
    lover: Optional[int] = None  # 情侣座位号
    idiot_revealed: bool = False  # 白痴是否已翻牌
    elder_lives: int = 2  # 长老生命数
    can_vote: bool = True  # 是否有投票权

    def to_public_dict(self) -> Dict[str, Any]:
        """Public info visible to all"""
        return {
            "seat": self.seat,
            "is_human": self.is_human,
            "avatar": self.avatar,
            "alive": self.alive,
            "model_name": self.model_name if not self.is_human else None,
            "personality_name": self.personality.name if self.personality else None,
        }

    def to_private_dict(self) -> Dict[str, Any]:
        """Private info for this player only"""
        data = self.to_public_dict()
        data["role"] = self.role.value
        data["camp"] = self.camp.value
        if self.role == Role.WITCH:
            data["has_heal"] = self.has_heal
            data["has_poison"] = self.has_poison
        if self.role == Role.SEER:
            data["seer_results"] = self.seer_results
        return data


class GameEngine:
    def __init__(self, game_id: str, config: Dict[str, Any], god_mode_password: Optional[str] = None):
        self.game_id = game_id
        self.config = config
        self.players: Dict[int, Player] = {}
        self.phase = GamePhase.WAITING
        self.day_count = 0
        self.night_count = 0
        self.paused = False
        self.winner: Optional[str] = None
        self.logs: List[Dict[str, Any]] = []
        self.start_time: Optional[datetime] = None
        
        # 上帝模式
        self.god_mode_password: Optional[str] = god_mode_password
        
        # 当前行动角色提示（用于前端展示"XXX请睁眼"）
        self.current_action_role: Optional[str] = None
        self.current_action_message: Optional[str] = None
        
        # 冥界复盘数据 - 死亡角色的虚拟行动记录（与真实对局完全隔离）
        self.phantom_actions: List[Dict[str, Any]] = []
        
        # Human action waiting
        self.waiting_for_human: Optional[int] = None
        self.human_action_type: Optional[str] = None
        self.human_action_options: Dict[str, Any] = {}
        self.human_response: Optional[Any] = None
        self.human_response_event = asyncio.Event()
        
        # Night results
        self.night_kill_target: Optional[int] = None
        self.night_healed: bool = False
        self.night_poisoned: Optional[int] = None
        self.night_guarded: Optional[int] = None
        
        # WebSocket broadcast callback
        self.broadcast: Optional[Callable] = None
        
        # LLM config
        api_config = config.get("api", {})
        self.api_base_url = api_config.get("base_url", "https://api.killerbest.com")
        self.api_key = api_config.get("api_key", "")
        self.default_timeout = api_config.get("default_timeout", 60)
        self.model_timeout_map = api_config.get("model_timeout_map", {})
        self.models_pool = normalize_model_ids(config.get("models", [
            "bl-DeepSeek-V3-250324",
            "bl-DeepSeek-V3.1-Terminus",
        ]))

    def set_broadcast(self, callback: Callable):
        """Set WebSocket broadcast callback"""
        self.broadcast = callback

    async def emit(self, event: str, data: Dict[str, Any], to_seat: Optional[int] = None):
        """Emit event via WebSocket"""
        if self.broadcast:
            await self.broadcast(event, data, to_seat)

    async def emit_state(self):
        """Broadcast full game state to all clients"""
        state = {
            "game_id": self.game_id,
            "phase": self.phase.value,
            "day_count": self.day_count,
            "night_count": self.night_count,
            "paused": self.paused,
            "winner": self.winner,
            "players": [p.to_public_dict() for p in self.players.values()],
            "alive_seats": [s for s, p in self.players.items() if p.alive],
            "logs": [log for log in self.logs if log.get("is_public", True)][-50:],
            "waiting_for_human": self.waiting_for_human,
            "human_action_type": self.human_action_type,
            "human_action_options": self.human_action_options,
            # 角色行动提示
            "current_action_role": self.current_action_role,
            "current_action_message": self.current_action_message,
        }
        await self.emit("state", state)
    
    async def announce_role_action(self, role_name: str, message: str, duration: float = 2.0):
        """广播角色行动提示（例如 '预言家请睁眼'）"""
        self.current_action_role = role_name
        self.current_action_message = message
        await self.emit_state()
        await asyncio.sleep(duration)
    
    async def clear_role_announcement(self):
        """清除角色行动提示"""
        self.current_action_role = None
        self.current_action_message = None
        await self.emit_state()
    
    def add_phantom_action(self, role: str, seat: int, action_type: str, 
                           target: Optional[int], decision: Optional[str], night: int):
        """记录死亡角色的虚拟行动（仅用于冥界复盘，不影响游戏）"""
        self.phantom_actions.append({
            "night": night,
            "role": role,
            "seat": seat,
            "action_type": action_type,
            "target": target,
            "decision": decision,
            "timestamp": datetime.now().isoformat(),
        })

    def add_log(self, log_type: str, content: str, seat: Optional[int] = None, is_public: bool = True):
        """Add log entry"""
        entry = {
            "type": log_type,
            "content": content,
            "seat": seat,
            "phase": self.phase.value,
            "day": self.day_count,
            "night": self.night_count,
            "time": datetime.now().isoformat(),
            "is_public": is_public,
        }
        self.logs.append(entry)
        return entry

    async def setup(self, human_seats: List[int], total_players: int = 12, num_wolves: int = 3, 
                    role_config: Dict[str, int] = None, avatars: List[str] = None,
                    random_models: bool = True, seat_model_map: Dict[int, str] = None):
        """Initialize game with players
        
        Args:
            human_seats: 真人玩家座位号列表
            total_players: 总玩家数
            num_wolves: 狼人数量（如果role_config未指定）
            role_config: 自定义角色配置，如 {"WOLF": 3, "SEER": 1, "WITCH": 1, "VILLAGER": 5}
            avatars: 头像列表
            random_models: 是否随机分配模型
            seat_model_map: 手动模型分配 {座位号: 模型名}
        """
        # Create role list
        if role_config:
            # 使用自定义角色配置
            roles = []
            role_map = {
                "WOLF": Role.WOLF,
                "VILLAGER": Role.VILLAGER,
                "SEER": Role.SEER,
                "WITCH": Role.WITCH,
                "HUNTER": Role.HUNTER,
                "GUARD": Role.GUARD,
                # 新增角色
                "CUPID": Role.CUPID,
                "IDIOT": Role.IDIOT,
                "ELDER": Role.ELDER,
                "WOLF_KING": Role.WOLF_KING,
                "WHITE_WOLF": Role.WHITE_WOLF,
                "BEAUTY": Role.BEAUTY,
            }
            for role_code, count in role_config.items():
                if role_code in role_map and count > 0:
                    roles.extend([role_map[role_code]] * count)
            
            # 如果配置的角色数量不足，补充村民
            while len(roles) < total_players:
                roles.append(Role.VILLAGER)
            # 如果配置的角色数量超出，截断
            roles = roles[:total_players]
        else:
            # 使用默认配置
            roles = (
                [Role.WOLF] * num_wolves +
                [Role.SEER, Role.WITCH, Role.GUARD, Role.HUNTER]
            )
            while len(roles) < total_players:
                roles.append(Role.VILLAGER)
        
        random.shuffle(roles)
        
        # Shuffle avatars
        if avatars:
            random.shuffle(avatars)
        
        # 狼人阵营角色列表
        wolf_roles = {Role.WOLF, Role.WOLF_KING, Role.WHITE_WOLF, Role.BEAUTY}
        
        # Create players
        for i in range(total_players):
            seat = i + 1
            role = roles[i]
            camp = Camp.WOLF if role in wolf_roles else Camp.GOOD
            is_human = seat in human_seats
            
            avatar = avatars[i] if avatars and i < len(avatars) else "1f642.webp"
            model_name = None
            personality = None
            
            if not is_human:
                # Model assignment: manual > random > first available
                if seat_model_map and seat in seat_model_map:
                    model_name = seat_model_map[seat]
                elif random_models and self.models_pool:
                    model_name = random.choice(self.models_pool)
                elif self.models_pool:
                    model_name = self.models_pool[0]
                else:
                    model_name = None
                personality = random.choice(PERSONALITIES)
            
            self.players[seat] = Player(
                seat=seat,
                role=role,
                camp=camp,
                is_human=is_human,
                model_name=model_name,
                personality=personality,
                avatar=avatar,
            )
        
        self.start_time = datetime.now()
        self.add_log("system", "游戏已创建，等待开始...")
        await self.emit_state()

    def get_alive_seats(self) -> List[int]:
        return [s for s, p in self.players.items() if p.alive]

    def get_alive_wolves(self) -> List[Player]:
        return [p for p in self.players.values() if p.alive and p.camp == Camp.WOLF]

    def get_alive_goods(self) -> List[Player]:
        return [p for p in self.players.values() if p.alive and p.camp == Camp.GOOD]

    def get_player_by_role(self, role: Role) -> Optional[Player]:
        for p in self.players.values():
            if p.role == role and p.alive:
                return p
        return None

    def check_winner(self) -> Optional[str]:
        """Check if game has ended"""
        wolves = self.get_alive_wolves()
        goods = self.get_alive_goods()
        
        if not wolves:
            return "好人阵营"
        if len(wolves) >= len(goods):
            return "狼人阵营"
        return None

    # ========== Human Action Handling ==========

    async def wait_for_human(self, seat: int, action_type: str, options: Dict[str, Any], timeout: int = 120) -> Any:
        """Wait for human player action"""
        self.waiting_for_human = seat
        self.human_action_type = action_type
        self.human_action_options = options
        self.human_response = None
        self.human_response_event.clear()
        
        await self.emit_state()
        
        # Also send private action request to the specific player
        await self.emit("action_required", {
            "seat": seat,
            "action_type": action_type,
            "options": options,
            "timeout": timeout,
        }, to_seat=seat)
        
        try:
            await asyncio.wait_for(self.human_response_event.wait(), timeout=timeout)
            response = self.human_response
        except asyncio.TimeoutError:
            response = None
            self.add_log("system", f"{seat}号玩家超时，自动跳过", seat=seat)
        
        self.waiting_for_human = None
        self.human_action_type = None
        self.human_action_options = {}
        await self.emit_state()
        
        return response

    def submit_human_action(self, seat: int, action_data: Any) -> bool:
        """Submit human player action"""
        if self.waiting_for_human != seat:
            return False
        self.human_response = action_data
        self.human_response_event.set()
        return True

    # ========== LLM Calls ==========

    async def call_llm(self, player: Player, messages: List[Dict]) -> Optional[str]:
        """Call LLM for AI player"""
        if not self.api_key:
            return None
        
        timeout = self.model_timeout_map.get(player.model_name, self.default_timeout)
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.api_base_url}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": player.model_name,
                        "messages": messages,
                        "temperature": 0.8,
                    },
                    timeout=timeout
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"LLM call failed for seat {player.seat}: {e}")
            return None

    async def call_llm_json(self, player: Player, messages: List[Dict]) -> Optional[Dict]:
        """Call LLM and parse JSON response"""
        text = await self.call_llm(player, messages)
        if not text:
            return None
        
        try:
            # Extract JSON from response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except:
            pass
        return None

    # ========== AI Night Action Generators ==========

    async def generate_ai_guard_action(self, guard: Player, candidates: List[int]) -> Optional[int]:
        """AI守卫决策"""
        if not candidates:
            return None
        
        context_lines = [
            f"当前是第{self.night_count}夜",
            f"你是{guard.seat}号守卫",
            f"存活玩家：{', '.join(str(s) for s in sorted(self.get_alive_seats()))}",
            f"可守护目标：{', '.join(str(c) for c in candidates)}",
            "",
            "昨天的发言和投票情况：",
        ]
        
        for log in self.logs[-30:]:
            if log["is_public"] and log["type"] in ["speech", "vote", "eliminate"]:
                if log["type"] == "speech":
                    context_lines.append(f"{log['seat']}号发言：{log['content']}")
                else:
                    context_lines.append(log['content'])
        
        messages = [
            {"role": "system", "content": f"""你是狼人杀游戏中的守卫，座位号{guard.seat}。
你的性格是：{guard.personality.name} - {guard.personality.description}

现在是夜晚，你需要选择一个玩家守护。被守护的玩家今晚不会被狼人杀死。
分析场上局势，选择你认为最可能被狼人袭击的重要玩家守护。

请直接回复一个数字，表示你要守护的座位号。只回复数字。"""},
            {"role": "user", "content": "\n".join(context_lines)}
        ]
        
        response = await self.call_llm(guard, messages)
        if response:
            try:
                import re
                numbers = re.findall(r'\d+', response)
                if numbers:
                    target = int(numbers[0])
                    if target in candidates:
                        return target
            except:
                pass
        
        return random.choice(candidates)

    async def generate_ai_wolf_action(self, wolves: List[Player], candidates: List[int]) -> Optional[int]:
        """AI狼人决策 - 由第一个存活的狼人代表决策"""
        if not candidates or not wolves:
            return None
        
        leader = wolves[0]
        wolf_seats = [w.seat for w in wolves]
        
        context_lines = [
            f"当前是第{self.night_count}夜",
            f"你是{leader.seat}号狼人",
            f"你的狼队友：{', '.join(str(s) for s in wolf_seats if s != leader.seat) or '无'}",
            f"存活的好人：{', '.join(str(c) for c in candidates)}",
            "",
            "昨天的发言和投票情况：",
        ]
        
        for log in self.logs[-30:]:
            if log["is_public"] and log["type"] in ["speech", "vote", "eliminate"]:
                if log["type"] == "speech":
                    context_lines.append(f"{log['seat']}号发言：{log['content']}")
                else:
                    context_lines.append(log['content'])
        
        messages = [
            {"role": "system", "content": f"""你是狼人杀游戏中的狼人，座位号{leader.seat}。
你的性格是：{leader.personality.name} - {leader.personality.description}

现在是夜晚，狼人需要选择一个好人击杀。
分析场上局势，优先击杀对狼人威胁最大的玩家（如预言家、女巫等神职）。

请直接回复一个数字，表示你们要击杀的座位号。只回复数字。"""},
            {"role": "user", "content": "\n".join(context_lines)}
        ]
        
        response = await self.call_llm(leader, messages)
        if response:
            try:
                import re
                numbers = re.findall(r'\d+', response)
                if numbers:
                    target = int(numbers[0])
                    if target in candidates:
                        return target
            except:
                pass
        
        return random.choice(candidates)

    async def generate_ai_seer_action(self, seer: Player, candidates: List[int]) -> Optional[int]:
        """AI预言家决策"""
        if not candidates:
            return None
        
        context_lines = [
            f"当前是第{self.night_count}夜",
            f"你是{seer.seat}号预言家",
            f"已查验结果：{seer.seer_results if seer.seer_results else '无'}",
            f"可查验目标：{', '.join(str(c) for c in candidates)}",
            "",
            "昨天的发言和投票情况：",
        ]
        
        for log in self.logs[-30:]:
            if log["is_public"] and log["type"] in ["speech", "vote", "eliminate"]:
                if log["type"] == "speech":
                    context_lines.append(f"{log['seat']}号发言：{log['content']}")
                else:
                    context_lines.append(log['content'])
        
        messages = [
            {"role": "system", "content": f"""你是狼人杀游戏中的预言家，座位号{seer.seat}。
你的性格是：{seer.personality.name} - {seer.personality.description}

现在是夜晚，你需要选择一个玩家查验其身份（狼人或好人）。
分析场上局势，选择你最怀疑或最需要确认身份的玩家。

请直接回复一个数字，表示你要查验的座位号。只回复数字。"""},
            {"role": "user", "content": "\n".join(context_lines)}
        ]
        
        response = await self.call_llm(seer, messages)
        if response:
            try:
                import re
                numbers = re.findall(r'\d+', response)
                if numbers:
                    target = int(numbers[0])
                    if target in candidates:
                        return target
            except:
                pass
        
        return random.choice(candidates)

    async def generate_ai_witch_heal(self, witch: Player, victim: int) -> bool:
        """AI女巫决策 - 是否救人"""
        context_lines = [
            f"当前是第{self.night_count}夜",
            f"你是{witch.seat}号女巫",
            f"今晚{victim}号被狼人袭击",
            f"你还有解药：{'是' if witch.has_heal else '否'}",
            f"你还有毒药：{'是' if witch.has_poison else '否'}",
            "",
            "昨天的发言和投票情况：",
        ]
        
        for log in self.logs[-30:]:
            if log["is_public"] and log["type"] in ["speech", "vote", "eliminate"]:
                if log["type"] == "speech":
                    context_lines.append(f"{log['seat']}号发言：{log['content']}")
                else:
                    context_lines.append(log['content'])
        
        messages = [
            {"role": "system", "content": f"""你是狼人杀游戏中的女巫，座位号{witch.seat}。
你的性格是：{witch.personality.name} - {witch.personality.description}

今晚{victim}号被狼人袭击。你需要决定是否使用解药救人。
解药只有一瓶，用完就没有了。

考虑因素：
- 被刀的人是否是重要角色（如预言家）
- 是否是第一晚（通常建议第一晚救人）
- 场上局势如何

请回复"是"或"否"，表示是否使用解药。只回复一个字。"""},
            {"role": "user", "content": "\n".join(context_lines)}
        ]
        
        response = await self.call_llm(witch, messages)
        if response:
            return "是" in response or "救" in response or "yes" in response.lower()
        
        # 默认第一晚救人
        return self.night_count == 1

    async def generate_ai_witch_poison(self, witch: Player, candidates: List[int]) -> Optional[int]:
        """AI女巫决策 - 是否毒人"""
        if not candidates:
            return None
        
        context_lines = [
            f"当前是第{self.night_count}夜",
            f"你是{witch.seat}号女巫",
            f"可毒杀目标：{', '.join(str(c) for c in candidates)}",
            "",
            "昨天的发言和投票情况：",
        ]
        
        for log in self.logs[-30:]:
            if log["is_public"] and log["type"] in ["speech", "vote", "eliminate"]:
                if log["type"] == "speech":
                    context_lines.append(f"{log['seat']}号发言：{log['content']}")
                else:
                    context_lines.append(log['content'])
        
        messages = [
            {"role": "system", "content": f"""你是狼人杀游戏中的女巫，座位号{witch.seat}。
你的性格是：{witch.personality.name} - {witch.personality.description}

你可以选择使用毒药毒死一个玩家，或者不使用。
毒药只有一瓶，用完就没有了。

考虑因素：
- 是否有明确的狼人目标
- 毒错好人的风险
- 通常建议在有把握时再用毒

如果要使用毒药，请回复要毒的座位号数字。
如果不使用毒药，请回复"不用"或"跳过"。"""},
            {"role": "user", "content": "\n".join(context_lines)}
        ]
        
        response = await self.call_llm(witch, messages)
        if response:
            if "不" in response or "跳" in response or "no" in response.lower():
                return None
            try:
                import re
                numbers = re.findall(r'\d+', response)
                if numbers:
                    target = int(numbers[0])
                    if target in candidates:
                        return target
            except:
                pass
        
        return None  # 默认不毒人

    # ========== Night Phase ==========

    async def run_night(self):
        """Execute night phase with role announcements and phantom actions"""
        self.night_count += 1
        self.phase = GamePhase.NIGHT
        self.night_kill_target = None
        self.night_healed = False
        self.night_poisoned = None
        
        self.add_log("phase", f"第{self.night_count}夜：天黑请闭眼")
        await self.emit_state()
        await asyncio.sleep(1.5)  # 给玩家准备时间
        
        # Guard action (with announcement and phantom)
        await self.announce_role_action("守卫", "守卫请睁眼，请选择你要守护的人")
        await self.guard_action_with_phantom()
        await self.announce_role_action("守卫", "守卫请闭眼", 1.5)
        
        # Wolf action (with announcement)
        await self.announce_role_action("狼人", "狼人请睁眼，请讨论并选择你们的猎杀目标")
        await self.wolf_action()
        await self.announce_role_action("狼人", "狼人请闭眼", 1.5)
        
        # Seer action (with announcement and phantom)
        await self.announce_role_action("预言家", "预言家请睁眼，请选择你要查验的人")
        await self.seer_action_with_phantom()
        await self.announce_role_action("预言家", "预言家请闭眼", 1.5)
        
        # Witch action (with announcement and phantom)
        await self.announce_role_action("女巫", "女巫请睁眼")
        await self.witch_action_with_phantom()
        await self.announce_role_action("女巫", "女巫请闭眼", 1.5)
        
        await self.clear_role_announcement()
        
        # Resolve night
        await self.resolve_night()

    def get_player_by_role_any(self, role: Role) -> Optional[Player]:
        """获取某角色的玩家（无论死活）"""
        for p in self.players.values():
            if p.role == role:
                return p
        return None

    async def guard_action_with_phantom(self):
        """守卫行动 - 包含死亡角色的虚拟行动用于时间混淆"""
        guard = self.get_player_by_role_any(Role.GUARD)
        if not guard:
            # 没有守卫角色，但仍需模拟等待时间
            await asyncio.sleep(random.uniform(3.0, 6.0))
            return
        
        candidates = [s for s in self.get_alive_seats() if s != guard.guard_last_target]
        
        if guard.alive:
            # 存活守卫 - 真实行动
            if guard.is_human:
                response = await self.wait_for_human(guard.seat, "guard", {
                    "candidates": candidates,
                    "message": "请选择今晚要守护的玩家（不能连续守护同一人）",
                })
                target = response.get("target") if response else None
            else:
                target = await self.generate_ai_guard_action(guard, candidates)
            
            if target and target in candidates:
                self.night_guarded = target
                guard.guard_last_target = target
                self.add_log("system", f"[上帝视角] 守卫{guard.seat}号守护了{target}号", seat=guard.seat, is_public=False)
        else:
            # 死亡守卫 - 虚拟行动（不计入游戏，仅用于时间混淆和冥界复盘）
            if not guard.is_human:
                phantom_target = await self.generate_ai_guard_action(guard, candidates)
                self.add_phantom_action("守卫", guard.seat, "guard", phantom_target, 
                                       f"守护{phantom_target}号" if phantom_target else "跳过",
                                       self.night_count)
            else:
                # 死亡的人类玩家也模拟等待
                await asyncio.sleep(random.uniform(3.0, 6.0))

    async def wolf_action(self):
        """Wolves choose kill target"""
        wolves = self.get_alive_wolves()
        if not wolves:
            return
        
        candidates = [s for s in self.get_alive_seats() if self.players[s].camp != Camp.WOLF]
        human_wolf = next((w for w in wolves if w.is_human), None)
        
        if human_wolf:
            response = await self.wait_for_human(human_wolf.seat, "wolf", {
                "candidates": candidates,
                "teammates": [w.seat for w in wolves if w.seat != human_wolf.seat],
                "message": "请选择今晚要击杀的目标",
            })
            target = response.get("target") if response else None
        else:
            # AI狼人 - 使用LLM决策
            target = await self.generate_ai_wolf_action(wolves, candidates)
        
        if target and target in candidates:
            self.night_kill_target = target
            # 狼人行动不公开，只记录在系统日志
            self.add_log("system", f"[上帝视角] 狼人选择击杀{target}号", is_public=False)

    async def seer_action_with_phantom(self):
        """预言家行动 - 包含死亡角色的虚拟行动"""
        seer = self.get_player_by_role_any(Role.SEER)
        if not seer:
            await asyncio.sleep(random.uniform(3.0, 6.0))
            return
        
        candidates = [s for s in self.get_alive_seats() if s != seer.seat and s not in seer.seer_results]
        
        if seer.alive:
            # 存活预言家 - 真实行动
            if seer.is_human:
                response = await self.wait_for_human(seer.seat, "seer", {
                    "candidates": candidates,
                    "known_results": seer.seer_results,
                    "message": "请选择要查验的玩家",
                })
                target = response.get("target") if response else None
            else:
                target = await self.generate_ai_seer_action(seer, candidates)
            
            if target and target in candidates:
                result = "狼人" if self.players[target].camp == Camp.WOLF else "好人"
                seer.seer_results[target] = result
                self.add_log("system", f"[上帝视角] 预言家{seer.seat}号查验{target}号，结果是【{result}】", seat=seer.seat, is_public=False)
                await self.emit("seer_result", {"target": target, "result": result}, to_seat=seer.seat)
        else:
            # 死亡预言家 - 虚拟行动（冥界复盘用）
            if not seer.is_human:
                phantom_target = await self.generate_ai_seer_action(seer, candidates)
                if phantom_target and phantom_target in candidates:
                    phantom_result = "狼人" if self.players[phantom_target].camp == Camp.WOLF else "好人"
                    self.add_phantom_action("预言家", seer.seat, "seer", phantom_target,
                                           f"查验{phantom_target}号，结果是【{phantom_result}】",
                                           self.night_count)
            else:
                await asyncio.sleep(random.uniform(3.0, 6.0))

    async def witch_action_with_phantom(self):
        """女巫行动 - 包含死亡角色的虚拟行动"""
        witch = self.get_player_by_role_any(Role.WITCH)
        if not witch:
            await asyncio.sleep(random.uniform(4.0, 8.0))
            return
        
        candidates = [s for s in self.get_alive_seats() if s != witch.seat]
        
        if witch.alive:
            # 存活女巫 - 真实行动
            # Heal
            if witch.has_heal and self.night_kill_target:
                if witch.is_human:
                    response = await self.wait_for_human(witch.seat, "witch_heal", {
                        "victim": self.night_kill_target,
                        "message": f"今晚{self.night_kill_target}号被刀，是否使用解药？",
                    })
                    use_heal = response.get("use_heal") if response else False
                else:
                    use_heal = await self.generate_ai_witch_heal(witch, self.night_kill_target)
                
                if use_heal:
                    witch.has_heal = False
                    self.night_healed = True
                    self.add_log("system", f"[上帝视角] 女巫{witch.seat}号救了{self.night_kill_target}号", seat=witch.seat, is_public=False)
            
            # Poison
            if witch.has_poison:
                if witch.is_human:
                    response = await self.wait_for_human(witch.seat, "witch_poison", {
                        "candidates": candidates,
                        "message": "是否使用毒药？选择目标或跳过",
                    })
                    target = response.get("target") if response else None
                else:
                    target = await self.generate_ai_witch_poison(witch, candidates)
                
                if target and target in candidates:
                    witch.has_poison = False
                    self.night_poisoned = target
                    self.add_log("system", f"[上帝视角] 女巫{witch.seat}号毒了{target}号", seat=witch.seat, is_public=False)
        else:
            # 死亡女巫 - 虚拟行动（冥界复盘用）
            if not witch.is_human:
                phantom_decisions = []
                # 虚拟救人决策
                if self.night_kill_target:
                    phantom_heal = await self.generate_ai_witch_heal(witch, self.night_kill_target)
                    phantom_decisions.append(f"{'救' if phantom_heal else '不救'}{self.night_kill_target}号")
                
                # 虚拟毒人决策
                phantom_poison = await self.generate_ai_witch_poison(witch, candidates)
                if phantom_poison:
                    phantom_decisions.append(f"毒{phantom_poison}号")
                else:
                    phantom_decisions.append("不使用毒药")
                
                self.add_phantom_action("女巫", witch.seat, "witch", phantom_poison,
                                       "；".join(phantom_decisions), self.night_count)
            else:
                await asyncio.sleep(random.uniform(4.0, 8.0))

    async def resolve_night(self):
        """Resolve night actions and announce deaths"""
        deaths = []
        
        # Wolf kill (unless healed or guarded)
        if self.night_kill_target:
            if self.night_healed:
                pass  # Saved
            elif self.night_guarded == self.night_kill_target:
                pass  # Protected
            else:
                self.players[self.night_kill_target].alive = False
                deaths.append(self.night_kill_target)
        
        # Witch poison
        if self.night_poisoned:
            self.players[self.night_poisoned].alive = False
            if self.night_poisoned not in deaths:
                deaths.append(self.night_poisoned)
        
        # Announce
        self.day_count += 1
        self.phase = GamePhase.DAY
        
        if deaths:
            death_str = "、".join(str(d) for d in sorted(deaths))
            self.add_log("death", f"第{self.day_count}天：天亮了，昨晚{death_str}号死亡")
        else:
            self.add_log("phase", f"第{self.day_count}天：天亮了，昨晚是平安夜")
        
        await self.emit_state()
        
        # Check hunter
        for seat in deaths:
            if self.players[seat].role == Role.HUNTER:
                await self.hunter_action(seat)

    # ========== Day Phase ==========

    async def run_day(self):
        """Execute day phase - speeches and voting"""
        self.add_log("phase", "开始白天发言环节")
        await self.emit_state()
        
        # Speeches
        for seat in sorted(self.get_alive_seats()):
            player = self.players[seat]
            
            if player.is_human:
                response = await self.wait_for_human(seat, "speech", {
                    "message": "请发言",
                    "timeout": 60,
                })
                speech = response.get("content", "（未发言）") if response else "（未发言）"
            else:
                speech = await self.generate_ai_speech(player)
            
            self.add_log("speech", speech, seat=seat)
            await self.emit_state()
            await asyncio.sleep(0.5)  # Brief pause between speeches
        
        # Voting
        await self.run_vote()

    def build_system_prompt(self, player: Player) -> str:
        """构建完整的系统提示词 - 参考原始代码"""
        base = f"""你正在玩"狼人杀"文字版推理游戏，你是 {player.seat} 号玩家。
你的真实身份：{player.role.value}，阵营：{player.camp.value}。
你必须努力让本阵营【获胜】作为最高目标，而不是搞破坏。

你的人格设定：{player.personality.name}
- 简介：{player.personality.description}

你需要在行为和发言中尽量贴合这个人格的风格，
但【不允许】为了演人格而故意自杀、自刀、自投或者明显出卖本阵营。

通用理性约束（非常重要）：
1. 白天投票时，一般不要投自己，除非你是狼人且清楚这样能立刻帮助狼阵营获胜。
2. 如果场上只有一个公开声称"预言家/女巫/守卫/猎人"的玩家，且没有明显证据证伪，
   作为好人阵营不应轻易把票集中在他身上。
3. 狼人夜晚选择刀人时，应优先考虑你认为的好人、强势发言者或关键神职，
   一般不要刀你认为是自己狼队队友的人。
4. 女巫使用解药和毒药要谨慎，解药通常优先救关键神职或你强认的好人；
   毒药优先给高概率是狼的目标。
5. 守卫在有限视角下要尽力守护你认为重要的好人（比如预言家、女巫、猎人），
   避免连续两夜守同一个人。
6. 猎人在白天被处决时开枪要尽量带走你最怀疑的狼人，而不是乱枪打自己阵营。
7. 任何时候都不要故意泄露自己狼队队友的身份，除非这是高度进阶的"切割"操作
   并且你确信这样能提高狼阵营的胜率。

你看到的公开信息都来自系统的【公开日志】总结，这些可以当作真实历史事实。
但你看不到夜晚的具体行动细节（谁刀谁、谁救谁等），除非规则允许你个人知道
（例如：女巫知道被刀的人、预言家知道自己查验的结果）。
如果你对局面理解不完整，可以承认信息有限，但不要胡编伪造不存在的事件。
"""
        return base.strip()

    async def generate_ai_speech(self, player: Player) -> str:
        """Generate AI player speech"""
        context = self.build_context_for_player(player)
        sys_prompt = self.build_system_prompt(player)
        
        # 构建额外信息
        extra_info_lines = []
        if player.role == Role.SEER and player.seer_results:
            extra_info_lines.append(
                "你是预言家，你个人掌握的查验结果为：" +
                ", ".join(f"{k}号={v}" for k, v in player.seer_results.items())
            )
        if player.role == Role.WITCH:
            extra_info_lines.append(
                f"你是女巫，目前解药剩余={'有' if player.has_heal else '无'}，毒药剩余={'有' if player.has_poison else '无'}。"
            )
        if player.role == Role.GUARD and player.guard_last_target:
            extra_info_lines.append(
                f"你是守卫，你上一夜守护了{player.guard_last_target}号。"
            )
        
        extra_info = "\n".join(extra_info_lines) or "你没有额外的隐藏信息。"
        
        user_prompt = f"""现在是白天发言阶段，请你作为 {player.seat} 号玩家进行一段简短发言（3~6 句），
体现你的身份立场和你的人格风格。

当前局面摘要：
{context}

你的额外隐藏信息（仅你自己知道）：
{extra_info}

发言要求：
- 必须以【我是X号，身份是（可以真报也可以隐藏/谎报）...】之类开头。
- 可以分析昨夜死亡、昨天投票、谁像好人/狼人，但不要虚构不存在的历史事件。
- 你的人格会影响你是激进、谨慎、阴阳怪气还是理性分析等，请贴合人格说话。
- 禁止直接说出"我看到系统日志 xxx 行"这种元信息。

最终只返回【你的中文发言文本】，不要写 JSON、不要写说明。"""
        
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self.call_llm(player, messages)
        return response if response else f"我是{player.seat}号，我暂时没有太多信息，只能先观望一下。"

    def build_context_for_player(self, player: Player) -> str:
        """Build game context for AI player"""
        lines = [
            f"这是第 {self.day_count} 天 / 第 {self.night_count} 夜之后的局面。",
            f"当前存活玩家座位号：{sorted(self.get_alive_seats())}。",
        ]
        
        # 添加昨夜死亡信息
        recent_deaths = [log for log in self.logs[-10:] if log["type"] == "death"]
        if recent_deaths:
            lines.append(f"昨夜死亡信息：{recent_deaths[-1]['content']}")
        
        lines.append("")
        lines.append("最近的公开日志（发言和投票）：")
        
        for log in self.logs[-30:]:
            if log["is_public"] and log["type"] in ["speech", "vote", "eliminate"]:
                if log["type"] == "speech":
                    lines.append(f"【{log['seat']}号发言】{log['content']}")
                else:
                    lines.append(log['content'])
        
        return "\n".join(lines)

    async def generate_ai_vote(self, player: Player, candidates: List[int], current_votes: Dict[int, int]) -> Optional[int]:
        """AI玩家投票决策 - 使用LLM"""
        # 构建投票上下文
        context_lines = [
            f"当前是第{self.day_count}天投票环节",
            f"你是{player.seat}号玩家，身份是{player.role.value}",
            f"存活玩家：{', '.join(str(s) for s in sorted(self.get_alive_seats()))}",
            f"可投票目标：{', '.join(str(c) for c in candidates)}",
            "",
        ]
        
        # 添加当前已有的投票情况
        if current_votes:
            context_lines.append("当前已投票情况：")
            for voter, target in current_votes.items():
                context_lines.append(f"  {voter}号 -> {target}号")
            context_lines.append("")
        
        # 添加今天的发言记录
        context_lines.append("今天的发言记录：")
        for log in self.logs:
            if log["is_public"] and log["type"] == "speech" and log.get("day") == self.day_count:
                context_lines.append(f"{log['seat']}号：{log['content']}")
        
        context = "\n".join(context_lines)
        
        sys_prompt = self.build_system_prompt(player)
        
        user_prompt = f"""现在进入白天投票阶段，你是 {player.seat} 号玩家，需要在所有仍然存活、且不是你自己的玩家中选择【一名要投票处决的目标】。

{context}

投票策略建议（理性约束）：
- 不要投自己（除非你是狼人并且非常确定自投可以让狼队立即获胜，这种情况极少）。
- 尽量投给你认为最可能是狼的人，而不是随便乱投。
- 如果场上只有一个公开自称预言家/女巫/守卫/猎人的玩家，且没有强证据证明他是假的，
  作为好人阵营不应轻易把票集中在他身上。
- 投票对象必须是当前存活玩家中、且不是你自己的座位号。

请只返回 JSON：
{{"target": 座位号整数}}"""
        
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self.call_llm(player, messages)
        
        if response:
            try:
                # 提取数字
                import re
                numbers = re.findall(r'\d+', response)
                if numbers:
                    target = int(numbers[0])
                    if target in candidates:
                        return target
            except:
                pass
        
        # 如果LLM失败，使用简单策略：跟随多数票或随机
        if current_votes:
            vote_counts = {}
            for t in current_votes.values():
                if t in candidates:
                    vote_counts[t] = vote_counts.get(t, 0) + 1
            if vote_counts:
                max_votes = max(vote_counts.values())
                top_targets = [t for t, c in vote_counts.items() if c == max_votes]
                return random.choice(top_targets)
        
        return random.choice(candidates) if candidates else None

    async def run_vote(self):
        """Execute voting phase - 顺序执行，每个投票后实时广播"""
        self.phase = GamePhase.VOTE
        self.add_log("phase", "开始投票环节")
        await self.emit_state()
        
        candidates = self.get_alive_seats()
        votes: Dict[int, int] = {}  # voter -> target
        
        for seat in sorted(self.get_alive_seats()):
            player = self.players[seat]
            valid_targets = [c for c in candidates if c != seat]
            
            if player.is_human:
                response = await self.wait_for_human(seat, "vote", {
                    "candidates": valid_targets,
                    "current_votes": votes.copy(),  # 传递当前投票情况
                    "message": "请投票",
                })
                target = response.get("target") if response else None
            else:
                # AI投票 - 使用LLM决策，传入当前投票情况
                target = await self.generate_ai_vote(player, valid_targets, votes)
            
            if target and target in valid_targets:
                votes[seat] = target
                self.add_log("vote", f"{seat}号投给了{target}号", seat=seat)
                # 每次投票后立即广播，让后面的玩家能看到
                await self.emit_state()
                await asyncio.sleep(0.3)  # 短暂延迟，让前端有时间显示
        
        # Count votes
        vote_counts: Dict[int, int] = {}
        for target in votes.values():
            vote_counts[target] = vote_counts.get(target, 0) + 1
        
        if vote_counts:
            max_votes = max(vote_counts.values())
            top_targets = [t for t, c in vote_counts.items() if c == max_votes]
            
            if len(top_targets) == 1:
                eliminated = top_targets[0]
                self.players[eliminated].alive = False
                self.add_log("eliminate", f"{eliminated}号被投票出局（{max_votes}票）")
                
                # Hunter
                if self.players[eliminated].role == Role.HUNTER:
                    await self.hunter_action(eliminated)
            else:
                self.add_log("vote", f"平票，无人出局")
        
        await self.emit_state()

    async def hunter_action(self, hunter_seat: int):
        """Hunter shoots on death"""
        hunter = self.players[hunter_seat]
        candidates = [s for s in self.get_alive_seats() if s != hunter_seat]
        
        if not candidates:
            return
        
        if hunter.is_human:
            response = await self.wait_for_human(hunter_seat, "hunter", {
                "candidates": candidates,
                "message": "你是猎人，死亡时可以开枪带走一人，是否开枪？",
            })
            target = response.get("target") if response else None
        else:
            target = random.choice(candidates)
        
        if target and target in candidates:
            self.players[target].alive = False
            self.add_log("hunter", f"猎人{hunter_seat}号开枪带走了{target}号", seat=hunter_seat)
            await self.emit_state()

    # ========== Main Game Loop ==========

    async def start(self):
        """Start the game"""
        if self.phase != GamePhase.WAITING:
            return
        
        self.add_log("system", "游戏开始！")
        await self.emit_state()
        
        # Send private role info to each player
        for seat, player in self.players.items():
            await self.emit("your_role", player.to_private_dict(), to_seat=seat)
        
        # Main loop
        while True:
            # Check pause
            while self.paused:
                await asyncio.sleep(1)
            
            # Night
            await self.run_night()
            
            winner = self.check_winner()
            if winner:
                await self.end_game(winner)
                return
            
            # Check pause
            while self.paused:
                await asyncio.sleep(1)
            
            # Day
            await self.run_day()
            
            winner = self.check_winner()
            if winner:
                await self.end_game(winner)
                return

    async def end_game(self, winner: str):
        """End the game"""
        self.phase = GamePhase.ENDED
        self.winner = winner
        self.add_log("end", f"游戏结束！{winner}获胜！")
        
        # Reveal all roles
        roles_info = []
        for seat in sorted(self.players.keys()):
            p = self.players[seat]
            roles_info.append(f"{seat}号：{p.role.value}")
        self.add_log("reveal", "身份揭晓：" + "，".join(roles_info))
        
        await self.emit_state()
        
        # 记录游戏统计
        await self._record_game_stats(winner)

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False
    
    async def _record_game_stats(self, winner: str):
        """记录游戏统计到持久化存储"""
        try:
            from game_stats import stats_manager
            
            end_time = datetime.now()
            duration = 0
            if self.start_time:
                duration = int((end_time - self.start_time).total_seconds())
            
            # 构建玩家信息
            players_info = []
            for seat, p in self.players.items():
                players_info.append({
                    "seat": seat,
                    "role": p.role.value,
                    "camp": p.camp.value,
                    "is_human": p.is_human,
                    "alive": p.alive,
                    "model_name": p.model_name,
                    "personality_name": p.personality.name if p.personality else None,
                })
            
            # 构建公开日志（过滤掉私密日志）
            public_logs = [
                {
                    "type": log["type"],
                    "content": log["content"],
                    "seat": log.get("seat"),
                    "day": log.get("day"),
                }
                for log in self.logs if log.get("is_public", True)
            ]
            
            # 构建游戏记录
            game_record = {
                "game_id": self.game_id,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": end_time.isoformat(),
                "duration": duration,
                "total_players": len(self.players),
                "num_wolves": len([p for p in self.players.values() if p.camp == Camp.WOLF]),
                "num_humans": len([p for p in self.players.values() if p.is_human]),
                "winner_camp": winner,
                "total_rounds": self.day_count,
                "players": players_info,
                "logs": public_logs,  # 添加日志
            }
            
            stats_manager.record_game(game_record)
            print(f"Game stats recorded: {self.game_id}")
        except Exception as e:
            print(f"Failed to record game stats: {e}")
