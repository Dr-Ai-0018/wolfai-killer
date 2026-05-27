"""
AI Werewolf Game Engine - Core game logic
Completely rewritten for WebSocket-first architecture
"""

import random
import json
import asyncio
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any, Set, Callable
from datetime import datetime
import httpx

from game_catalog import (
    Camp,
    DEFAULT_MODEL_POOL,
    PERSONALITIES,
    PERSONALITY_MAP,
    Personality,
    Role,
    WOLF_ROLES,
    normalize_model_ids,
)
from game_review import (
    ROLE_CLAIM_KEYWORDS,
    build_day_summary as summarize_day_state,
    build_public_claim_summary as summarize_public_claims,
    extract_speech_meta as extract_public_speech_meta,
)
from game_resolution import (
    determine_winner,
    find_lover_chain_target,
    resolve_immediate_elimination_rule,
    should_disable_powers_for_elder,
    awaken_wild_children,
)
from game_setup import assign_mason_peers, build_player_specs


class GamePhase(Enum):
    WAITING = "waiting"
    NIGHT = "night"
    DAY = "day"
    VOTE = "vote"
    ENDED = "ended"


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
    fox_checks: Dict[int, str] = field(default_factory=dict)
    fox_power_active: bool = True
    angel_active: bool = True
    scapegoat_allow_voters: List[int] = field(default_factory=list)
    # 新角色属性
    lover: Optional[int] = None  # 情侣座位号
    idiot_revealed: bool = False  # 白痴是否已翻牌
    elder_lives: int = 2  # 长老生命数
    can_vote: bool = True  # 是否有投票权
    idol: Optional[int] = None  # 野孩子认定的榜样
    wild_child_awakened: bool = False  # 榜样死亡后是否转狼
    mason_peers: List[int] = field(default_factory=list)  # 共济会同伴
    cursed_turned: bool = False  # 被诅咒者是否已转狼
    blessing_used: bool = False  # 受祝福者是否已抵挡过一次袭击

    def to_public_dict(self) -> Dict[str, Any]:
        """Public info visible to all"""
        data = {
            "seat": self.seat,
            "is_human": self.is_human,
            "avatar": self.avatar,
            "alive": self.alive,
            "model_name": self.model_name if not self.is_human else None,
            "personality_name": self.personality.name if self.personality else None,
        }
        if self.idiot_revealed:
            data["revealed_role"] = self.role.value
            data["can_vote"] = self.can_vote
        return data

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
        if self.role == Role.FOX:
            data["fox_checks"] = self.fox_checks
            data["fox_power_active"] = self.fox_power_active
        if self.role == Role.ANGEL:
            data["angel_active"] = self.angel_active
        if self.role == Role.SCAPEGOAT:
            data["scapegoat_allow_voters"] = list(self.scapegoat_allow_voters)
        if self.lover:
            data["lover"] = self.lover
        if self.role == Role.ELDER:
            data["elder_lives"] = self.elder_lives
        if self.role == Role.IDIOT:
            data["can_vote"] = self.can_vote
        if self.role == Role.WILD_CHILD:
            data["idol"] = self.idol
            data["wild_child_awakened"] = self.wild_child_awakened
        if self.role == Role.MASON:
            data["mason_peers"] = list(self.mason_peers)
        if self.role == Role.CURSED:
            data["cursed_turned"] = self.cursed_turned
        if self.role == Role.BLESSED:
            data["blessing_used"] = self.blessing_used
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
        self.log_sequence = 0
        self.start_time: Optional[datetime] = None
        self.angel_victory_seat: Optional[int] = None
        self.restricted_voters_next_day: Optional[set[int]] = None
        
        # 上帝模式
        self.god_mode_password: Optional[str] = god_mode_password
        
        # 当前行动角色提示（用于前端展示"XXX请睁眼"）
        self.current_action_role: Optional[str] = None
        self.current_action_message: Optional[str] = None
        
        # 冥界复盘数据 - 死亡角色的虚拟行动记录（与真实对局完全隔离）
        self.phantom_actions: List[Dict[str, Any]] = []
        self.powers_disabled = False
        self.cupid_paired = False
        
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
        self.api_base_url = str(api_config.get("base_url", "https://api.killerbest.com")).rstrip("/")
        self.api_v1_base_url = self.api_base_url if self.api_base_url.endswith("/v1") else f"{self.api_base_url}/v1"
        self.api_key = api_config.get("api_key", "")
        self.default_timeout = api_config.get("default_timeout", 60)
        self.model_timeout_map = api_config.get("model_timeout_map", {})
        self.models_pool = normalize_model_ids(config.get("models", DEFAULT_MODEL_POOL))

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
            "day_summary": self.build_day_summary(),
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

    def add_log(
        self,
        log_type: str,
        content: str,
        seat: Optional[int] = None,
        is_public: bool = True,
        meta: Optional[Dict[str, Any]] = None,
    ):
        """Add log entry"""
        self.log_sequence += 1
        entry = {
            "seq": self.log_sequence,
            "type": log_type,
            "content": content,
            "seat": seat,
            "phase": self.phase.value,
            "day": self.day_count,
            "night": self.night_count,
            "time": datetime.now().isoformat(),
            "is_public": is_public,
            "visibility": "public" if is_public else "private",
            "meta": meta or {},
        }
        self.logs.append(entry)
        return entry

    @staticmethod
    def extract_speech_meta(speech: str) -> Dict[str, Any]:
        return extract_public_speech_meta(speech, ROLE_CLAIM_KEYWORDS)

    def build_public_claim_summary(self) -> Dict[str, List[int]]:
        return summarize_public_claims(self.logs, self.get_alive_seats())

    def build_vote_scores(self, player: Player, candidates: List[int], current_votes: Dict[int, int]) -> Dict[int, int]:
        """Heuristic score for day voting to reduce blind dogpiles."""
        scores = {candidate: 0 for candidate in candidates}
        claims = self.build_public_claim_summary()
        protected_claimants = {
            seat
            for role_name, seats in claims.items()
            if len(seats) == 1 and role_name in {Role.SEER.value, Role.WITCH.value, Role.GUARD.value, Role.HUNTER.value}
            for seat in seats
        }

        for target in current_votes.values():
            if target in scores:
                scores[target] += 1
        current_vote_counts: Dict[int, int] = {}
        for target in current_votes.values():
            current_vote_counts[target] = current_vote_counts.get(target, 0) + 1

        today_speeches = [
            log for log in self.logs
            if log.get("is_public") and log.get("type") == "speech" and log.get("day") == self.day_count
        ]
        suspicion_speakers: Dict[int, set[int]] = {candidate: set() for candidate in candidates}
        defense_speakers: Dict[int, set[int]] = {candidate: set() for candidate in candidates}
        role_conflict_speakers: Dict[int, set[int]] = {candidate: set() for candidate in candidates}
        early_pressure_speakers: Dict[int, set[int]] = {candidate: set() for candidate in candidates}
        anti_dogpile_speakers: Dict[int, set[int]] = {candidate: set() for candidate in candidates}
        for log in today_speeches:
            speaker = int(log.get("seat") or 0)
            content = str(log.get("content") or "")
            meta = log.get("meta") or {}
            for candidate in candidates:
                if f"{candidate}号" not in content:
                    continue
                scores[candidate] += 1
                if any(keyword in content for keyword in ["像狼", "可疑", "问题最大", "压力位", "投"]):
                    scores[candidate] += 2
                    suspicion_speakers[candidate].add(speaker)
                    if speaker != candidate and any(keyword in content for keyword in ["压力位", "追问", "优先", "先给"]):
                        early_pressure_speakers[candidate].add(speaker)
                if any(keyword in content for keyword in ["好人", "暂不投", "先不出", "站边"]):
                    scores[candidate] -= 1
                    defense_speakers[candidate].add(speaker)
                if any(keyword in content for keyword in ["别空跟票", "别跟票", "独立判断", "别无脑冲", "别急着", "先听", "先看"]):
                    anti_dogpile_speakers[candidate].add(speaker)
                if any(keyword in content for keyword in ["对跳", "假预言家", "悍跳", "穿衣服", "不信这个预言家", "不信这个女巫", "不信这个守卫", "不信这个猎人"]):
                    role_conflict_speakers[candidate].add(speaker)
            if speaker in scores and meta.get("claimed_role"):
                scores[speaker] -= 2

        if player.role == Role.SEER:
            for checked_seat, result in player.seer_results.items():
                if checked_seat in scores and result == "狼人":
                    scores[checked_seat] += 100
                elif checked_seat in scores and result == "好人":
                    scores[checked_seat] -= 100
        if player.role == Role.FOX:
            for checked_seat, result in player.fox_checks.items():
                if result == "没有狼人":
                    for seat in self.get_neighbor_triplet(checked_seat):
                        if seat in scores:
                            scores[seat] -= 25

        for claimant in protected_claimants:
            if claimant in scores and player.camp == Camp.GOOD:
                scores[claimant] -= 8

        if player.camp == Camp.GOOD:
            for candidate in candidates:
                if candidate in protected_claimants and not role_conflict_speakers[candidate]:
                    # A sole public power-role claim should be very hard to execute without a real contradiction.
                    scores[candidate] -= 8

                # Reduce first-day / low-evidence dogpiles on early pressure targets.
                if (
                    self.day_count <= 2
                    and len(suspicion_speakers[candidate]) <= 2
                    and len(defense_speakers[candidate]) >= 1
                    and current_vote_counts.get(candidate, 0) == 0
                ):
                    scores[candidate] -= 3

                # If a target is mostly being pushed by vote momentum rather than multiple independent speeches,
                # good camp should resist piling on.
                vote_pressure = current_vote_counts.get(candidate, 0)
                if vote_pressure >= 2 and len(suspicion_speakers[candidate]) <= 1:
                    scores[candidate] -= 4

                # In small lobbies, an early pressure caller should not be auto-executed
                # unless multiple independent speakers actually articulate why that caller is wolfy.
                if (
                    self.total_players <= 5
                    and self.day_count <= 2
                    and candidate in scores
                ):
                    callers_targeting_others = {
                        speaker for targeted_seat, speakers in early_pressure_speakers.items()
                        if targeted_seat != candidate
                        for speaker in speakers
                    }
                    if (
                        callers_targeting_others
                        and candidate in callers_targeting_others
                        and len(suspicion_speakers[candidate] - {candidate}) <= 1
                        and not role_conflict_speakers[candidate]
                    ):
                        scores[candidate] -= 4

                # Do not over-credit a counter-pusher merely for sounding like
                # they value independent judgment or anti-dogpile process.
                if (
                    self.total_players <= 5
                    and self.day_count <= 2
                    and current_vote_counts.get(candidate, 0) == 0
                    and len(anti_dogpile_speakers[candidate]) >= 1
                    and len(suspicion_speakers[candidate] - anti_dogpile_speakers[candidate]) == 0
                ):
                    scores[candidate] -= 2

                # Do not execute a claimed seer lightly when they produced at least one public check and there is no counterclaim.
                if (
                    candidate in claims.get(Role.SEER.value, [])
                    and len(claims.get(Role.SEER.value, [])) == 1
                    and not role_conflict_speakers[candidate]
                ):
                    scores[candidate] -= 10

        if player.camp == Camp.WOLF:
            teammates = {ally.seat for ally in self.get_alive_wolves()}
            for teammate in teammates:
                if teammate in scores:
                    scores[teammate] -= 100
        return scores

    def build_day_summary(self) -> Dict[str, Any]:
        return summarize_day_state(
            logs=self.logs,
            alive_seats=self.get_alive_seats(),
            day_count=self.day_count,
            phase=self.phase.value,
        )

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
        player_specs = build_player_specs(
            total_players=total_players,
            human_seats=human_seats,
            num_wolves=num_wolves,
            models_pool=self.models_pool,
            role_config=role_config,
            avatars=avatars,
            random_models=random_models,
            seat_model_map=seat_model_map,
        )

        for spec in player_specs:
            self.players[spec["seat"]] = Player(**spec)

        assign_mason_peers(self.players)
        
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
        return determine_winner(self.players, self.angel_victory_seat)

    def disable_good_powers(self) -> None:
        if self.powers_disabled:
            return
        self.powers_disabled = True
        self.add_log("system", "长老以非狼人袭击的方式死亡，村庄神职能力失效。")

    def should_disable_powers_for_elder(self, cause: str) -> bool:
        return should_disable_powers_for_elder(cause)

    async def awaken_wild_children_for_idol(self, dead_seat: int) -> list[int]:
        awakened = awaken_wild_children(self.players, dead_seat)
        for seat in awakened:
            self.add_log(
                "wild_child_awaken",
                f"[上帝视角] {seat}号野孩子因榜样死亡转入狼人阵营",
                seat=seat,
                is_public=False,
                meta={"seat": seat, "idol": dead_seat, "action": "awaken"},
            )
            await self.emit("wild_child_awakened", {"idol": dead_seat}, to_seat=seat)
        return awakened

    async def eliminate_player(
        self,
        seat: int,
        cause: str,
        allow_hunter: bool = True,
        context: Optional[Dict[str, Any]] = None,
    ) -> list[int]:
        player = self.players[seat]
        if not player.alive:
            return []
        context = context or {}

        immediate_effect = resolve_immediate_elimination_rule(player, cause, self.day_count)
        if immediate_effect and immediate_effect.kind == "angel_victory":
            self.angel_victory_seat = seat
            self.add_log(
                "angel_victory",
                f"{seat}号天使在开局阶段达成了自己的死亡胜利条件。",
                seat=seat,
                meta={"seat": seat, "role": player.role.value, "cause": cause, "winner": "天使阵营"},
            )
            return [seat]
        if immediate_effect and immediate_effect.kind == "elder_survive":
            self.add_log(
                "system",
                f"{seat}号长老承受了第一次狼人袭击，侥幸存活。",
                meta={"seat": seat, "role": player.role.value, "cause": cause, "elder_lives": player.elder_lives},
            )
            return []
        if immediate_effect and immediate_effect.kind == "blessed_survive":
            self.add_log(
                "system",
                f"{seat}号受祝福者抵挡了第一次狼人袭击，侥幸存活。",
                meta={"seat": seat, "role": player.role.value, "cause": cause, "blessing_used": True},
            )
            return []
        if immediate_effect and immediate_effect.kind == "cursed_turn":
            self.add_log(
                "system",
                f"{seat}号被狼人诅咒后未死亡，已秘密转入狼人阵营。",
                seat=seat,
                is_public=False,
                meta={"seat": seat, "role": player.role.value, "cause": cause, "action": "turn_wolf"},
            )
            await self.emit("cursed_turned", {"camp": Camp.WOLF.value}, to_seat=seat)
            return []
        if immediate_effect and immediate_effect.kind == "idiot_reveal":
            self.add_log(
                "reveal",
                f"{seat}号被票出时翻牌为白痴，免于出局，但此后失去投票权。",
                meta={"seat": seat, "role": player.role.value, "cause": cause, "can_vote": False},
            )
            return []

        player.alive = False
        eliminated = [seat]

        if player.role == Role.ELDER and self.should_disable_powers_for_elder(cause):
            self.disable_good_powers()

        lover_seat = find_lover_chain_target(self.players, seat)
        if lover_seat:
            lover = self.players[lover_seat]
            lover.alive = False
            eliminated.append(lover_seat)
            self.add_log(
                "system",
                f"{lover_seat}号因情侣殉情而死亡。",
                meta={"seat": lover_seat, "cause": "lover_suicide", "lover_of": seat},
            )
            if lover.role == Role.ELDER and self.should_disable_powers_for_elder("lover_suicide"):
                self.disable_good_powers()

        awakened_children: list[int] = []
        for eliminated_seat in list(eliminated):
            awakened_children.extend(await self.awaken_wild_children_for_idol(eliminated_seat))
        if awakened_children:
            self.add_log(
                "system",
                "有野孩子在榜样死亡后秘密转化为狼人。",
                is_public=False,
                meta={"awakened": awakened_children, "eliminated": list(eliminated)},
            )

        if cause == "vote" and player.role == Role.SUPER_SAINT:
            last_voter = context.get("last_voter")
            if isinstance(last_voter, int):
                target = self.players.get(last_voter)
                if target and target.alive:
                    eliminated.extend(
                        await self.eliminate_player(
                            last_voter,
                            "super_saint",
                            allow_hunter=allow_hunter,
                            context={"triggered_by": seat},
                        )
                    )
                    self.add_log(
                        "super_saint",
                        f"{seat}号圣徒被公投出局后发动反噬，带走了最后投票的{last_voter}号。",
                        seat=seat,
                        meta={"seat": seat, "target": last_voter, "cause": "vote"},
                    )

        if allow_hunter:
            for eliminated_seat in list(eliminated):
                eliminated_player = self.players[eliminated_seat]
                if eliminated_player.role == Role.HUNTER and not self.powers_disabled:
                    await self.hunter_action(eliminated_seat)

        return eliminated

    async def scapegoat_choose_voters(self, scapegoat_seat: int) -> list[int]:
        scapegoat = self.players[scapegoat_seat]
        alive_others = [seat for seat in self.get_alive_seats() if seat != scapegoat_seat]
        allowed: list[int] = []

        if not alive_others:
            scapegoat.scapegoat_allow_voters = []
            self.restricted_voters_next_day = set()
            return []

        if scapegoat.is_human:
            response = await self.wait_for_human(scapegoat_seat, "scapegoat", {
                "candidates": alive_others,
                "message": "你是替罪羊，请选择下一天仍然保有投票权的玩家（可多选）",
            })
            raw_allowed = response.get("allowed_voters") if response else None
            if isinstance(raw_allowed, list):
                parsed: list[int] = []
                for item in raw_allowed:
                    try:
                        seat_num = int(item)
                    except (TypeError, ValueError):
                        continue
                    if seat_num in alive_others and seat_num not in parsed:
                        parsed.append(seat_num)
                allowed = parsed
        else:
            allowed = alive_others[: max(1, min(2, len(alive_others)))]

        if not allowed:
            allowed = alive_others[:1]

        scapegoat.scapegoat_allow_voters = list(allowed)
        self.restricted_voters_next_day = set(allowed)
        self.add_log(
            "scapegoat_choice",
            f"{scapegoat_seat}号替罪羊指定下一天仅有{ '、'.join(f'{seat}号' for seat in allowed) }保有投票权。",
            seat=scapegoat_seat,
            meta={"seat": scapegoat_seat, "allowed_voters": allowed},
        )
        return allowed

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

    def build_prompt_cache_key(self, player: Player, cache_namespace: str) -> str:
        """Keep a stable cache key per game, seat, model, and interaction type."""
        raw_key = f"{self.game_id}|seat:{player.seat}|model:{player.model_name}|ns:{cache_namespace}"
        return "wolf-" + hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:32]

    @staticmethod
    def extract_response_text(response: Dict[str, Any]) -> str:
        """Extract final text from a Responses API payload."""
        output_text = response.get("output_text")
        if isinstance(output_text, str) and output_text:
            return output_text

        parts: List[str] = []
        for item in response.get("output", []) or []:
            for content in item.get("content", []) or []:
                if content.get("type") == "output_text":
                    parts.append(content.get("text", ""))
        return "".join(parts).strip()

    @staticmethod
    def extract_cached_tokens(response: Dict[str, Any]) -> int:
        """Support both input_tokens_details and prompt_tokens_details usage layouts."""
        usage = response.get("usage") or {}
        return int(
            ((usage.get("input_tokens_details") or {}).get("cached_tokens"))
            or ((usage.get("prompt_tokens_details") or {}).get("cached_tokens"))
            or 0
        )

    # ========== LLM Calls ==========

    async def call_llm(self, player: Player, messages: List[Dict], cache_namespace: str = "generic") -> Optional[str]:
        """Call the streaming Responses API for an AI player."""
        if not self.api_key:
            return None

        timeout = self.model_timeout_map.get(player.model_name, self.default_timeout)

        instructions = "\n\n".join(
            str(message.get("content", "")).strip()
            for message in messages
            if message.get("role") == "system" and str(message.get("content", "")).strip()
        ).strip()
        input_messages = [
            {
                "role": message.get("role", "user"),
                "content": message.get("content", ""),
            }
            for message in messages
            if message.get("role") != "system"
        ]
        payload: Dict[str, Any] = {
            "model": player.model_name,
            "input": input_messages,
            "temperature": 0.8,
            "stream": True,
            "store": False,
            "prompt_cache_key": self.build_prompt_cache_key(player, cache_namespace),
        }
        if instructions:
            payload["instructions"] = instructions

        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self.api_v1_base_url}/responses",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "Accept": "text/event-stream",
                    },
                    json=payload,
                    timeout=timeout,
                ) as resp:
                    resp.raise_for_status()

                    event_name = ""
                    data_lines: List[str] = []
                    created: Optional[Dict[str, Any]] = None
                    completed: Optional[Dict[str, Any]] = None

                    async for line in resp.aiter_lines():
                        if line == "":
                            if data_lines:
                                data = "".join(data_lines)
                                data_lines = []
                                if data != "[DONE]":
                                    parsed = json.loads(data)
                                    if event_name == "response.created":
                                        created = parsed.get("response")
                                    elif event_name == "response.completed":
                                        completed = parsed.get("response")
                            event_name = ""
                            continue
                        if line.startswith(":"):
                            continue
                        if line.startswith("event:"):
                            event_name = line[6:].strip()
                            continue
                        if line.startswith("data:"):
                            data_lines.append(line[5:].lstrip())

                    if data_lines:
                        data = "".join(data_lines)
                        if data != "[DONE]":
                            parsed = json.loads(data)
                            if event_name == "response.created":
                                created = parsed.get("response")
                            elif event_name == "response.completed":
                                completed = parsed.get("response")

            if completed is None:
                raise RuntimeError("missing response.completed event")

            usage = completed.get("usage") or {}
            cached_tokens = self.extract_cached_tokens(completed)
            prompt_cache_key = completed.get("prompt_cache_key") or (created or {}).get("prompt_cache_key")
            self.add_log(
                "llm_trace",
                (
                    f"seat={player.seat} model={player.model_name} ns={cache_namespace} "
                    f"prompt_cache_key={prompt_cache_key} input_tokens={int(usage.get('input_tokens') or 0)} "
                    f"cached_tokens={cached_tokens} output_tokens={int(usage.get('output_tokens') or 0)}"
                ),
                seat=player.seat,
                is_public=False,
                meta={
                    "seat": player.seat,
                    "model": player.model_name,
                    "cache_namespace": cache_namespace,
                    "prompt_cache_key": prompt_cache_key,
                    "input_tokens": int(usage.get("input_tokens") or 0),
                    "cached_tokens": cached_tokens,
                    "output_tokens": int(usage.get("output_tokens") or 0),
                },
            )
            return self.extract_response_text(completed)
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
        
        response = await self.call_llm(guard, messages, cache_namespace="night-guard")
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
        
        response = await self.call_llm(leader, messages, cache_namespace="night-wolf")
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
        
        response = await self.call_llm(seer, messages, cache_namespace="night-seer")
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
        claim_summary = self.build_public_claim_summary()
        sole_seer_claim = claim_summary.get(Role.SEER.value, [])
        small_lobby_single_wolf = len(self.players) == 5 and len([p for p in self.players.values() if p.camp == Camp.WOLF]) == 1

        context_lines = [
            f"当前是第{self.night_count}夜",
            f"你是{witch.seat}号女巫",
            f"今晚{victim}号被狼人袭击",
            f"你还有解药：{'是' if witch.has_heal else '否'}",
            f"你还有毒药：{'是' if witch.has_poison else '否'}",
            f"当前公开预言家声明：{sole_seer_claim if sole_seer_claim else '无'}",
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
- 是否是第一晚
- 场上局势如何
- 如果是5人单狼小局，不要机械地“第一晚必救”。
- 在5人单狼小局里，更适合救的情况是：
  1. 刀口落在你自己
  2. 刀口落在场上唯一可信的预言家
  3. 刀口落在你强认的关键好人，且不救会让狼直接滚起节奏
- 如果只是普通民牌且信息还没明朗，保留解药往往比首夜直接交掉更稳。

请回复"是"或"否"，表示是否使用解药。只回复一个字。"""},
            {"role": "user", "content": "\n".join(context_lines)}
        ]
        
        response = await self.call_llm(witch, messages, cache_namespace="night-witch-heal")
        if response:
            return "是" in response or "救" in response or "yes" in response.lower()
        
        if small_lobby_single_wolf:
            if victim == witch.seat:
                return True
            if sole_seer_claim and victim in sole_seer_claim:
                return True
            return False

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
        
        response = await self.call_llm(witch, messages, cache_namespace="night-witch-poison")
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

        if self.night_count == 1:
            await self.announce_role_action("野孩子", "野孩子请睁眼，请选择一名玩家作为你的榜样")
            await self.wild_child_action()
            await self.announce_role_action("野孩子", "野孩子请闭眼", 1.5)

        if self.night_count == 1 and not self.cupid_paired:
            await self.announce_role_action("丘比特", "丘比特请睁眼，请选择两名玩家成为情侣")
            await self.cupid_action()
            await self.announce_role_action("丘比特", "丘比特请闭眼", 1.5)
        
        # Guard action (with announcement and phantom)
        if not self.powers_disabled:
            await self.announce_role_action("守卫", "守卫请睁眼，请选择你要守护的人")
            await self.guard_action_with_phantom()
            await self.announce_role_action("守卫", "守卫请闭眼", 1.5)
        
        # Wolf action (with announcement)
        await self.announce_role_action("狼人", "狼人请睁眼，请讨论并选择你们的猎杀目标")
        await self.wolf_action()
        await self.announce_role_action("狼人", "狼人请闭眼", 1.5)

        if not self.powers_disabled:
            await self.announce_role_action("狐狸", "狐狸请睁眼，请选择一名玩家进行邻座嗅探")
            await self.fox_action_with_phantom()
            await self.announce_role_action("狐狸", "狐狸请闭眼", 1.5)
        
        # Seer action (with announcement and phantom)
        if not self.powers_disabled:
            await self.announce_role_action("预言家", "预言家请睁眼，请选择你要查验的人")
            await self.seer_action_with_phantom()
            await self.announce_role_action("预言家", "预言家请闭眼", 1.5)
        
        # Witch action (with announcement and phantom)
        if not self.powers_disabled:
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

    async def cupid_action(self):
        cupid = self.get_player_by_role_any(Role.CUPID)
        if not cupid:
            await asyncio.sleep(random.uniform(2.0, 4.0))
            return

        candidates = self.get_alive_seats()
        pair: list[int] = []

        if cupid.alive:
            if cupid.is_human:
                response = await self.wait_for_human(cupid.seat, "cupid", {
                    "candidates": candidates,
                    "message": "请选择两名玩家成为情侣",
                })
                raw_pair = response.get("pair") if response else None
                if isinstance(raw_pair, list):
                    pair = [int(item) for item in raw_pair if int(item) in candidates]
            else:
                pair = random.sample(candidates, 2) if len(candidates) >= 2 else []
        else:
            if not cupid.is_human:
                pair = random.sample(candidates, 2) if len(candidates) >= 2 else []
                self.add_phantom_action("丘比特", cupid.seat, "cupid", None, f"连接{pair[0]}号与{pair[1]}号" if len(pair) == 2 else "跳过", self.night_count)
            else:
                await asyncio.sleep(random.uniform(2.0, 4.0))
            return

        if len(pair) != 2 or pair[0] == pair[1]:
            available = [seat for seat in candidates]
            pair = random.sample(available, 2) if len(available) >= 2 else []

        if len(pair) == 2:
            first, second = pair
            self.players[first].lover = second
            self.players[second].lover = first
            self.cupid_paired = True
            self.add_log(
                "cupid_action",
                f"[上帝视角] 丘比特连接了{first}号与{second}号",
                seat=cupid.seat,
                is_public=False,
                meta={"actor_role": "丘比特", "pair": sorted(pair), "action": "pair"},
            )
            for seat in pair:
                await self.emit("lover_info", {"lover": self.players[seat].lover}, to_seat=seat)

    async def wild_child_action(self):
        wild_child = self.get_player_by_role_any(Role.WILD_CHILD)
        if not wild_child or wild_child.idol is not None:
            await asyncio.sleep(random.uniform(2.0, 4.0))
            return

        candidates = [seat for seat in self.get_alive_seats() if seat != wild_child.seat]
        idol: Optional[int] = None

        if wild_child.alive:
            if wild_child.is_human:
                response = await self.wait_for_human(wild_child.seat, "wild_child", {
                    "candidates": candidates,
                    "message": "请选择一名玩家作为你的榜样；若他死亡，你将转入狼人阵营",
                })
                raw_target = response.get("target") if response else None
                if raw_target is not None:
                    try:
                        parsed = int(raw_target)
                    except (TypeError, ValueError):
                        parsed = None
                    if parsed in candidates:
                        idol = parsed
            else:
                idol = random.choice(candidates) if candidates else None
        else:
            if not wild_child.is_human:
                idol = random.choice(candidates) if candidates else None
                self.add_phantom_action("野孩子", wild_child.seat, "wild_child", idol, f"认{idol}号为榜样" if idol else "跳过", self.night_count)
            else:
                await asyncio.sleep(random.uniform(2.0, 4.0))
            return

        if idol not in candidates:
            idol = random.choice(candidates) if candidates else None

        if idol is not None:
            wild_child.idol = idol
            self.add_log(
                "wild_child_action",
                f"[上帝视角] {wild_child.seat}号野孩子认定了{idol}号为榜样",
                seat=wild_child.seat,
                is_public=False,
                meta={"actor_role": "野孩子", "idol": idol, "action": "idol"},
            )
            await self.emit("wild_child_info", {"idol": idol}, to_seat=wild_child.seat)

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
                self.add_log(
                    "guard_action",
                    f"[上帝视角] 守卫{guard.seat}号守护了{target}号",
                    seat=guard.seat,
                    is_public=False,
                    meta={"actor_role": "守卫", "target": target, "action": "guard"},
                )
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
            self.add_log(
                "wolf_action",
                f"[上帝视角] 狼人选择击杀{target}号",
                is_public=False,
                meta={"actor_role": "狼人", "target": target, "action": "kill"},
            )

    def get_neighbor_triplet(self, center_seat: int) -> list[int]:
        ordered = sorted(self.players.keys())
        if center_seat not in ordered:
            return [center_seat]
        if len(ordered) <= 2:
            return ordered
        idx = ordered.index(center_seat)
        left = ordered[(idx - 1) % len(ordered)]
        right = ordered[(idx + 1) % len(ordered)]
        return [left, center_seat, right]

    async def fox_action_with_phantom(self):
        """狐狸行动 - 私有邻座嗅探，若没嗅到狼人则永久失去能力"""
        fox = self.get_player_by_role_any(Role.FOX)
        if not fox:
            await asyncio.sleep(random.uniform(3.0, 6.0))
            return

        candidates = self.get_alive_seats()

        if fox.alive and fox.fox_power_active:
            if fox.is_human:
                response = await self.wait_for_human(fox.seat, "fox", {
                    "candidates": candidates,
                    "known_results": fox.fox_checks,
                    "message": "请选择一名玩家；你会嗅探该玩家及其左右邻座中是否存在狼人",
                })
                target = response.get("target") if response else None
            else:
                target = random.choice(candidates) if candidates else None

            if target and target in candidates:
                checked = self.get_neighbor_triplet(target)
                found_wolf = any(self.players[seat].camp == Camp.WOLF for seat in checked)
                result = "有狼人" if found_wolf else "没有狼人"
                fox.fox_checks[target] = result
                self.add_log(
                    "fox_action",
                    f"[上帝视角] 狐狸{fox.seat}号嗅探了{target}号相邻区域，结果为【{result}】",
                    seat=fox.seat,
                    is_public=False,
                    meta={
                        "actor_role": "狐狸",
                        "target": target,
                        "checked": checked,
                        "result": result,
                        "action": "sniff",
                    },
                )
                await self.emit("fox_result", {"target": target, "checked": checked, "result": result}, to_seat=fox.seat)
                if not found_wolf:
                    fox.fox_power_active = False
                    self.add_log(
                        "fox_action",
                        f"[上帝视角] 狐狸{fox.seat}号未嗅到狼人，失去了后续嗅探能力。",
                        seat=fox.seat,
                        is_public=False,
                        meta={"actor_role": "狐狸", "target": target, "checked": checked, "action": "lose_power"},
                    )
        else:
            if not fox.is_human and fox.fox_power_active:
                phantom_target = random.choice(candidates) if candidates else None
                if phantom_target:
                    self.add_phantom_action("狐狸", fox.seat, "fox", phantom_target, f"嗅探{phantom_target}号周边", self.night_count)
            else:
                await asyncio.sleep(random.uniform(3.0, 6.0))

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
                self.add_log(
                    "seer_action",
                    f"[上帝视角] 预言家{seer.seat}号查验{target}号，结果是【{result}】",
                    seat=seer.seat,
                    is_public=False,
                    meta={"actor_role": "预言家", "target": target, "result": result, "action": "check"},
                )
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
                    self.add_log(
                        "witch_action",
                        f"[上帝视角] 女巫{witch.seat}号救了{self.night_kill_target}号",
                        seat=witch.seat,
                        is_public=False,
                        meta={"actor_role": "女巫", "target": self.night_kill_target, "action": "heal"},
                    )
            
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
                    self.add_log(
                        "witch_action",
                        f"[上帝视角] 女巫{witch.seat}号毒了{target}号",
                        seat=witch.seat,
                        is_public=False,
                        meta={"actor_role": "女巫", "target": target, "action": "poison"},
                    )
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
                eliminated = await self.eliminate_player(self.night_kill_target, "wolf_kill")
                for seat in eliminated:
                    if seat not in deaths:
                        deaths.append(seat)
        
        # Witch poison
        if self.night_poisoned:
            eliminated = await self.eliminate_player(self.night_poisoned, "poison")
            for seat in eliminated:
                if seat not in deaths:
                    deaths.append(seat)
        
        # Announce
        self.day_count += 1
        self.phase = GamePhase.DAY
        
        if deaths:
            death_str = "、".join(str(d) for d in sorted(deaths))
            self.add_log(
                "death",
                f"第{self.day_count}天：天亮了，昨晚{death_str}号死亡",
                meta={"deaths": sorted(deaths)},
            )
        else:
            self.add_log("phase", f"第{self.day_count}天：天亮了，昨晚是平安夜")
        
        await self.emit_state()

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
            
            self.add_log("speech", speech, seat=seat, meta=self.extract_speech_meta(speech))
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
        if player.role == Role.FOX:
            if player.fox_checks:
                extra_info_lines.append(
                    "你是狐狸，你掌握的嗅探结果为：" +
                    ", ".join(f"围绕{k}号={v}" for k, v in player.fox_checks.items()) +
                    f"。你当前{'仍然可以' if player.fox_power_active else '已经不能再'}继续嗅探。"
                )
            else:
                extra_info_lines.append(
                    f"你是狐狸。每晚可以选择一名玩家，嗅探该玩家及其左右邻座中是否存在狼人；若某次结果为没有狼人，你将失去后续嗅探能力。你当前{'仍然可以' if player.fox_power_active else '已经不能再'}继续嗅探。"
                )
        if player.role == Role.ANGEL:
            extra_info_lines.append(
                f"你是天使。若你在首夜被狼人袭击，或在第1天白天被公投出局，你将立刻单独获胜。你当前{'仍然保有' if player.angel_active else '已经失去'}这个开局胜利条件。"
            )
        if player.role == Role.WITCH:
            extra_info_lines.append(
                f"你是女巫，目前解药剩余={'有' if player.has_heal else '无'}，毒药剩余={'有' if player.has_poison else '无'}。"
            )
        if player.role == Role.GUARD and player.guard_last_target:
            extra_info_lines.append(
                f"你是守卫，你上一夜守护了{player.guard_last_target}号。"
            )
        if player.role == Role.MASON:
            if player.mason_peers:
                extra_info_lines.append(
                    "你是共济会成员，你已知的同伴是：" +
                    "、".join(f"{seat}号" for seat in player.mason_peers) + "。"
                )
            else:
                extra_info_lines.append("你是共济会成员，但当前没有存活或配置中的其他共济会同伴。")
        if player.role == Role.WILD_CHILD:
            if player.idol:
                extra_info_lines.append(
                    f"你是野孩子，你首夜认定的榜样是{player.idol}号。"
                    f"{' 该榜样已死，你现在属于狼人阵营。' if player.wild_child_awakened else ' 如果该榜样死亡，你会转入狼人阵营。'}"
                )
            else:
                extra_info_lines.append("你是野孩子，你需要在首夜认定一名榜样；若榜样死亡，你将转入狼人阵营。")
        if player.role == Role.CURSED:
            extra_info_lines.append(
                "你是被诅咒者，初始属于好人阵营。若你被狼人袭击且此前未转化，你不会死亡，而会秘密转入狼人阵营。"
            )
        if player.role == Role.BLESSED:
            extra_info_lines.append(
                f"你是受祝福者，你{'已经' if player.blessing_used else '尚未'}抵挡过一次狼人袭击。"
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
- 不要因为某个人第一个强势发言就机械跟冲，至少给出一条具体理由。
- 如果你是好人且场上只有一个神职单跳、还没有明显硬伤，不要轻易带头把他票出。
- 如果当前是 5 人或 6 人小局，且你是预言家/女巫/守卫/猎人这类关键好人身份，不要发得过于含糊。
  你应该更明确地给出站边、查验、资源态度或你反对今天出谁的理由，避免好人因为信息太软被狼带票。
- 如果当前是 5 人或 6 人小局，即使你只是普通村民，也不要只说“先看看”“先观望”这种空话。
  你至少要给出一个当前压力位，或者明确说明你暂时更信谁、为什么。
- 如果你是预言家并且已经有查验结果，优先把查验信息和今天的出票方向说清楚。
- 如果你是女巫或守卫，在小局里即使不明说夜间细节，也要明确提醒大家别在低信息轮次乱推关键位。
- 你的人格会影响你是激进、谨慎、阴阳怪气还是理性分析等，请贴合人格说话。
- 禁止直接说出"我看到系统日志 xxx 行"这种元信息。

最终只返回【你的中文发言文本】，不要写 JSON、不要写说明。"""
        
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self.call_llm(player, messages, cache_namespace="day-speech")
        if response:
            return response

        alive_candidates = [seat for seat in sorted(self.get_alive_seats()) if seat != player.seat]
        fallback_target = alive_candidates[0] if alive_candidates else None
        if fallback_target is None:
            return f"我是{player.seat}号，信息不多，但我会继续听大家把逻辑讲清楚。"
        return (
            f"我是{player.seat}号，我先给一个临时压力位：{fallback_target}号。"
            " 现在信息还不够满，但我不接受只说观望不落点。"
            " 后面谁的发言更像回避判断、谁更像顺势跟票，我就继续追这个方向。"
        )

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

        claim_summary = self.build_public_claim_summary()
        if claim_summary:
            parts = [f"{role}：{','.join(str(seat) + '号' for seat in seats)}" for role, seats in sorted(claim_summary.items())]
            lines.append("当前公开身份声明：" + "；".join(parts))

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
        claim_summary = self.build_public_claim_summary()
        if claim_summary:
            context_lines.append("")
            context_lines.append("当前公开身份声明：")
            for role_name, seats in sorted(claim_summary.items()):
                context_lines.append(f"  {role_name} -> {', '.join(str(seat) + '号' for seat in seats)}")
        
        context = "\n".join(context_lines)
        
        sys_prompt = self.build_system_prompt(player)
        
        user_prompt = f"""现在进入白天投票阶段，你是 {player.seat} 号玩家，需要在所有仍然存活、且不是你自己的玩家中选择【一名要投票处决的目标】。

{context}

投票策略建议（理性约束）：
- 不要投自己（除非你是狼人并且非常确定自投可以让狼队立即获胜，这种情况极少）。
- 尽量投给你认为最可能是狼的人，而不是随便乱投。
- 如果场上只有一个公开自称预言家/女巫/守卫/猎人的玩家，且没有强证据证明他是假的，
  作为好人阵营不应轻易把票集中在他身上。
- 不要因为前置位某个玩家发言很强势，就机械地把票跟上去；至少确认对方给了具体逻辑。
- 如果你没有足够证据，不要把票挂在“唯一神职单跳”身上，优先从发言空、跟票重、立场飘的人里选。
- 投票对象必须是当前存活玩家中、且不是你自己的座位号。

请只返回 JSON：
{{"target": 座位号整数}}"""
        
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self.call_llm(player, messages, cache_namespace="day-vote")
        
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
        
        scores = self.build_vote_scores(player, candidates, current_votes)
        if scores:
            ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
            top_score = ranked[0][1]
            top_targets = [seat for seat, score in ranked if score == top_score]
            if top_score > -50:
                return random.choice(top_targets)
        return random.choice(candidates) if candidates else None

    async def run_vote(self):
        """Execute voting phase - 顺序执行，每个投票后实时广播"""
        self.phase = GamePhase.VOTE
        self.add_log("phase", "开始投票环节")
        await self.emit_state()
        
        candidates = self.get_alive_seats()
        votes: Dict[int, int] = {}  # voter -> target
        last_voter_by_target: Dict[int, int] = {}
        active_restriction = set(self.restricted_voters_next_day or set())
        if self.restricted_voters_next_day is not None:
            self.restricted_voters_next_day = None
        for seat in self.get_alive_seats():
            player = self.players[seat]
            player.can_vote = not active_restriction or seat in active_restriction
        
        for seat in sorted(self.get_alive_seats()):
            player = self.players[seat]
            if not player.can_vote:
                self.add_log("vote", f"{seat}号本轮无投票权，自动跳过", seat=seat, meta={"voter": seat, "skipped": True})
                await self.emit_state()
                await asyncio.sleep(0.3)
                continue
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
                last_voter_by_target[target] = seat
                self.add_log(
                    "vote",
                    f"{seat}号投给了{target}号",
                    seat=seat,
                    meta={"voter": seat, "target": target},
                )
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
                eliminated_chain = await self.eliminate_player(
                    eliminated,
                    "vote",
                    context={"last_voter": last_voter_by_target.get(eliminated)},
                )
                if eliminated_chain:
                    self.add_log(
                        "eliminate",
                        f"{eliminated}号被投票出局（{max_votes}票）",
                        meta={"eliminated": eliminated, "votes": max_votes, "vote_counts": vote_counts, "chain": eliminated_chain},
                    )
                else:
                    self.add_log(
                        "vote_result",
                        f"{eliminated}号获得最多票（{max_votes}票），但未实际出局。",
                        meta={"seat": eliminated, "votes": max_votes, "vote_counts": vote_counts, "eliminated": False},
                    )
            else:
                scapegoat = self.get_player_by_role(Role.SCAPEGOAT)
                if scapegoat:
                    scapegoat_seat = scapegoat.seat
                    eliminated_chain = await self.eliminate_player(
                        scapegoat_seat,
                        "scapegoat",
                        allow_hunter=False,
                        context={"tie_targets": list(top_targets)},
                    )
                    await self.scapegoat_choose_voters(scapegoat_seat)
                    self.add_log(
                        "eliminate",
                        f"平票后，{scapegoat_seat}号替罪羊替死出局。",
                        meta={"eliminated": scapegoat_seat, "tie_targets": top_targets, "vote_counts": vote_counts, "chain": eliminated_chain},
                    )
                else:
                    self.add_log("vote", f"平票，无人出局", meta={"vote_counts": vote_counts, "tie_targets": top_targets})
        
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
            self.add_log(
                "hunter",
                f"猎人{hunter_seat}号开枪带走了{target}号",
                seat=hunter_seat,
                meta={"hunter": hunter_seat, "target": target},
            )
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
            
            public_logs = [log for log in self.logs if log.get("is_public", True)]
            private_logs = [log for log in self.logs if not log.get("is_public", True)]
            log_counts: Dict[str, int] = {}
            for log in self.logs:
                log_type = str(log.get("type") or "unknown")
                log_counts[log_type] = log_counts.get(log_type, 0) + 1

            llm_traces = [log for log in private_logs if log.get("type") == "llm_trace"]
            total_input_tokens = sum(int((log.get("meta") or {}).get("input_tokens") or 0) for log in llm_traces)
            total_cached_tokens = sum(int((log.get("meta") or {}).get("cached_tokens") or 0) for log in llm_traces)
            total_output_tokens = sum(int((log.get("meta") or {}).get("output_tokens") or 0) for log in llm_traces)
            
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
                "logs": public_logs,
                "public_logs": public_logs,
                "private_logs": private_logs,
                "day_summary": self.build_day_summary(),
                "log_counts": log_counts,
                "llm_usage_summary": {
                    "request_count": len(llm_traces),
                    "input_tokens": total_input_tokens,
                    "cached_tokens": total_cached_tokens,
                    "output_tokens": total_output_tokens,
                },
                "phantom_actions": list(self.phantom_actions),
            }
            
            stats_manager.record_game(game_record)
            print(f"Game stats recorded: {self.game_id}")
        except Exception as e:
            print(f"Failed to record game stats: {e}")
