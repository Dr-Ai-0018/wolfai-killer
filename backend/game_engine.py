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
from game_ai_context import (
    build_context_for_player as summarize_player_context,
    build_extra_role_info,
    build_system_prompt as build_ai_system_prompt,
    build_vote_context,
)
from game_day import build_human_speech_options, build_speech_log, resolve_human_speech
from game_day_ai import (
    build_day_speech_user_prompt,
    build_day_vote_scores,
    build_day_vote_user_prompt,
    build_llm_messages,
    choose_speech_fallback,
    choose_vote_fallback,
    parse_ai_vote_response,
)
from game_end import build_end_game_logs, build_game_record
from game_night_ai import (
    build_guard_messages,
    build_seer_messages,
    build_witch_heal_messages,
    build_witch_poison_messages,
    build_wolf_messages,
    parse_night_target_response,
    parse_witch_poison_response,
    should_use_heal_response,
    should_witch_heal_fallback,
)
from game_night_actions import (
    build_fox_action_log,
    build_fox_lose_power_log,
    build_fox_phantom_summary,
    build_fox_result_payload,
    build_guard_action_log,
    build_guard_phantom_summary,
    build_seer_action_log,
    build_seer_phantom_summary,
    build_seer_result_payload,
    build_witch_heal_log,
    build_witch_phantom_summary,
    build_witch_poison_log,
    build_wolf_action_log,
    parse_human_target_response,
    parse_human_witch_heal_response,
)
from game_night_resolution import append_unique_deaths, build_night_announcement, should_apply_wolf_kill
from game_vote import (
    apply_vote_rights,
    build_cast_vote_log,
    build_human_vote_options,
    build_skipped_vote_log,
    build_scapegoat_tie_log,
    build_valid_vote_targets,
    build_vote_eliminate_log,
    build_vote_result_log,
    build_vote_tie_log,
    record_vote_choice,
    resolve_vote_round,
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
from game_phantom import pick_random_candidate, run_phantom_role_action
from game_special_roles import (
    apply_cupid_pair,
    apply_wild_child_idol,
    build_cupid_action_log,
    build_cupid_phantom_decision,
    build_lover_info_payload,
    build_wild_child_action_log,
    build_wild_child_info_payload,
    build_wild_child_phantom_decision,
    choose_cupid_pair,
    choose_wild_child_idol,
    parse_cupid_pair_response,
    parse_wild_child_target_response,
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
        return build_day_vote_scores(
            player=player,
            candidates=candidates,
            current_votes=current_votes,
            claims=self.build_public_claim_summary(),
            logs=self.logs,
            day_count=self.day_count,
            total_players=self.total_players,
            get_neighbor_triplet=self.get_neighbor_triplet,
            alive_wolf_seats=[ally.seat for ally in self.get_alive_wolves()],
        )

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
        messages = build_guard_messages(guard, self.night_count, self.get_alive_seats(), candidates, self.logs)
        response = await self.call_llm(guard, messages, cache_namespace="night-guard")
        target = parse_night_target_response(response, candidates)
        return target if target is not None else random.choice(candidates)

    async def generate_ai_wolf_action(self, wolves: List[Player], candidates: List[int]) -> Optional[int]:
        """AI狼人决策 - 由第一个存活的狼人代表决策"""
        if not candidates or not wolves:
            return None
        leader = wolves[0]
        messages = build_wolf_messages(leader, wolves, self.night_count, candidates, self.logs)
        response = await self.call_llm(leader, messages, cache_namespace="night-wolf")
        target = parse_night_target_response(response, candidates)
        return target if target is not None else random.choice(candidates)

    async def generate_ai_seer_action(self, seer: Player, candidates: List[int]) -> Optional[int]:
        """AI预言家决策"""
        if not candidates:
            return None
        messages = build_seer_messages(seer, self.night_count, candidates, self.logs)
        response = await self.call_llm(seer, messages, cache_namespace="night-seer")
        target = parse_night_target_response(response, candidates)
        return target if target is not None else random.choice(candidates)

    async def generate_ai_witch_heal(self, witch: Player, victim: int) -> bool:
        """AI女巫决策 - 是否救人"""
        claim_summary = self.build_public_claim_summary()
        sole_seer_claim = claim_summary.get(Role.SEER.value, [])
        small_lobby_single_wolf = len(self.players) == 5 and len([p for p in self.players.values() if p.camp == Camp.WOLF]) == 1
        messages = build_witch_heal_messages(witch, self.night_count, victim, sole_seer_claim, self.logs)
        response = await self.call_llm(witch, messages, cache_namespace="night-witch-heal")
        if response:
            return should_use_heal_response(response)
        return should_witch_heal_fallback(
            self.night_count,
            victim,
            witch.seat,
            sole_seer_claim,
            small_lobby_single_wolf,
        )

    async def generate_ai_witch_poison(self, witch: Player, candidates: List[int]) -> Optional[int]:
        """AI女巫决策 - 是否毒人"""
        if not candidates:
            return None
        messages = build_witch_poison_messages(witch, self.night_count, candidates, self.logs)
        response = await self.call_llm(witch, messages, cache_namespace="night-witch-poison")
        return parse_witch_poison_response(response, candidates)

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
        requested_pair: Optional[list[int]] = None

        if cupid.alive:
            if cupid.is_human:
                response = await self.wait_for_human(cupid.seat, "cupid", {
                    "candidates": candidates,
                    "message": "请选择两名玩家成为情侣",
                })
                requested_pair = parse_cupid_pair_response(response, candidates)
            else:
                requested_pair = choose_cupid_pair(candidates)
        else:
            if not cupid.is_human:
                pair = choose_cupid_pair(candidates)
                self.add_phantom_action("丘比特", cupid.seat, "cupid", None, build_cupid_phantom_decision(pair), self.night_count)
            else:
                await asyncio.sleep(random.uniform(2.0, 4.0))
            return

        pair = choose_cupid_pair(candidates, requested_pair)

        if apply_cupid_pair(self.players, pair):
            self.cupid_paired = True
            payload = build_cupid_action_log(cupid.seat, pair)
            self.add_log(payload["type"], payload["content"], seat=payload["seat"], is_public=False, meta=payload["meta"])
            for seat in pair:
                await self.emit("lover_info", build_lover_info_payload(self.players[seat].lover), to_seat=seat)

    async def wild_child_action(self):
        wild_child = self.get_player_by_role_any(Role.WILD_CHILD)
        if not wild_child or wild_child.idol is not None:
            await asyncio.sleep(random.uniform(2.0, 4.0))
            return

        candidates = [seat for seat in self.get_alive_seats() if seat != wild_child.seat]
        requested_idol: Optional[int] = None

        if wild_child.alive:
            if wild_child.is_human:
                response = await self.wait_for_human(wild_child.seat, "wild_child", {
                    "candidates": candidates,
                    "message": "请选择一名玩家作为你的榜样；若他死亡，你将转入狼人阵营",
                })
                requested_idol = parse_wild_child_target_response(response, candidates)
            else:
                requested_idol = choose_wild_child_idol(candidates)
        else:
            if not wild_child.is_human:
                idol = choose_wild_child_idol(candidates)
                self.add_phantom_action("野孩子", wild_child.seat, "wild_child", idol, build_wild_child_phantom_decision(idol), self.night_count)
            else:
                await asyncio.sleep(random.uniform(2.0, 4.0))
            return

        idol = choose_wild_child_idol(candidates, requested_idol)

        if apply_wild_child_idol(wild_child, idol):
            payload = build_wild_child_action_log(wild_child.seat, idol)
            self.add_log(payload["type"], payload["content"], seat=payload["seat"], is_public=False, meta=payload["meta"])
            await self.emit("wild_child_info", build_wild_child_info_payload(idol), to_seat=wild_child.seat)

    async def guard_action_with_phantom(self):
        """守卫行动 - 包含死亡角色的虚拟行动用于时间混淆"""
        guard = self.get_player_by_role_any(Role.GUARD)

        async def run_live_action():
            candidates = [s for s in self.get_alive_seats() if s != guard.guard_last_target]
            if guard.is_human:
                response = await self.wait_for_human(guard.seat, "guard", {
                    "candidates": candidates,
                    "message": "请选择今晚要守护的玩家（不能连续守护同一人）",
                })
                target = parse_human_target_response(response, candidates)
            else:
                target = await self.generate_ai_guard_action(guard, candidates)
            
            if target and target in candidates:
                self.night_guarded = target
                guard.guard_last_target = target
                payload = build_guard_action_log(guard.seat, target)
                self.add_log(payload["type"], payload["content"], seat=payload["seat"], is_public=False, meta=payload["meta"])

        async def run_dead_ai_phantom():
            candidates = [s for s in self.get_alive_seats() if s != guard.guard_last_target]
            phantom_target = await self.generate_ai_guard_action(guard, candidates)
            self.add_phantom_action(
                "守卫",
                guard.seat,
                "guard",
                phantom_target,
                build_guard_phantom_summary(phantom_target),
                self.night_count,
            )

        await run_phantom_role_action(guard, (3.0, 6.0), run_live_action, run_dead_ai_phantom)

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
            target = parse_human_target_response(response, candidates)
        else:
            # AI狼人 - 使用LLM决策
            target = await self.generate_ai_wolf_action(wolves, candidates)
        
        if target and target in candidates:
            self.night_kill_target = target
            # 狼人行动不公开，只记录在系统日志
            payload = build_wolf_action_log(target)
            self.add_log(payload["type"], payload["content"], is_public=False, meta=payload["meta"])

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

        async def run_live_action():
            if not fox.fox_power_active:
                return
            candidates = self.get_alive_seats()
            if fox.is_human:
                response = await self.wait_for_human(fox.seat, "fox", {
                    "candidates": candidates,
                    "known_results": fox.fox_checks,
                    "message": "请选择一名玩家；你会嗅探该玩家及其左右邻座中是否存在狼人",
                })
                target = parse_human_target_response(response, candidates)
            else:
                target = random.choice(candidates) if candidates else None

            if target and target in candidates:
                checked = self.get_neighbor_triplet(target)
                found_wolf = any(self.players[seat].camp == Camp.WOLF for seat in checked)
                result = "有狼人" if found_wolf else "没有狼人"
                fox.fox_checks[target] = result
                payload = build_fox_action_log(fox.seat, target, checked, result)
                self.add_log(payload["type"], payload["content"], seat=payload["seat"], is_public=False, meta=payload["meta"])
                await self.emit("fox_result", build_fox_result_payload(target, checked, result), to_seat=fox.seat)
                if not found_wolf:
                    fox.fox_power_active = False
                    payload = build_fox_lose_power_log(fox.seat, target, checked)
                    self.add_log(payload["type"], payload["content"], seat=payload["seat"], is_public=False, meta=payload["meta"])

        async def run_dead_ai_phantom():
            if not fox.fox_power_active:
                return
            candidates = self.get_alive_seats()
            phantom_target = pick_random_candidate(candidates)
            if phantom_target:
                self.add_phantom_action("狐狸", fox.seat, "fox", phantom_target, build_fox_phantom_summary(phantom_target), self.night_count)

        await run_phantom_role_action(fox, (3.0, 6.0), run_live_action, run_dead_ai_phantom)

    async def seer_action_with_phantom(self):
        """预言家行动 - 包含死亡角色的虚拟行动"""
        seer = self.get_player_by_role_any(Role.SEER)

        async def run_live_action():
            candidates = [s for s in self.get_alive_seats() if s != seer.seat and s not in seer.seer_results]
            if seer.is_human:
                response = await self.wait_for_human(seer.seat, "seer", {
                    "candidates": candidates,
                    "known_results": seer.seer_results,
                    "message": "请选择要查验的玩家",
                })
                target = parse_human_target_response(response, candidates)
            else:
                target = await self.generate_ai_seer_action(seer, candidates)
            
            if target and target in candidates:
                result = "狼人" if self.players[target].camp == Camp.WOLF else "好人"
                seer.seer_results[target] = result
                payload = build_seer_action_log(seer.seat, target, result)
                self.add_log(payload["type"], payload["content"], seat=payload["seat"], is_public=False, meta=payload["meta"])
                await self.emit("seer_result", build_seer_result_payload(target, result), to_seat=seer.seat)

        async def run_dead_ai_phantom():
            candidates = [s for s in self.get_alive_seats() if s != seer.seat and s not in seer.seer_results]
            phantom_target = await self.generate_ai_seer_action(seer, candidates)
            if phantom_target and phantom_target in candidates:
                phantom_result = "狼人" if self.players[phantom_target].camp == Camp.WOLF else "好人"
                self.add_phantom_action(
                    "预言家",
                    seer.seat,
                    "seer",
                    phantom_target,
                    build_seer_phantom_summary(phantom_target, phantom_result),
                    self.night_count,
                )

        await run_phantom_role_action(seer, (3.0, 6.0), run_live_action, run_dead_ai_phantom)

    async def witch_action_with_phantom(self):
        """女巫行动 - 包含死亡角色的虚拟行动"""
        witch = self.get_player_by_role_any(Role.WITCH)

        async def run_live_action():
            candidates = [s for s in self.get_alive_seats() if s != witch.seat]
            if witch.has_heal and self.night_kill_target:
                if witch.is_human:
                    response = await self.wait_for_human(witch.seat, "witch_heal", {
                        "victim": self.night_kill_target,
                        "message": f"今晚{self.night_kill_target}号被刀，是否使用解药？",
                    })
                    use_heal = parse_human_witch_heal_response(response)
                else:
                    use_heal = await self.generate_ai_witch_heal(witch, self.night_kill_target)
                
                if use_heal:
                    witch.has_heal = False
                    self.night_healed = True
                    payload = build_witch_heal_log(witch.seat, self.night_kill_target)
                    self.add_log(payload["type"], payload["content"], seat=payload["seat"], is_public=False, meta=payload["meta"])

            if witch.has_poison:
                if witch.is_human:
                    response = await self.wait_for_human(witch.seat, "witch_poison", {
                        "candidates": candidates,
                        "message": "是否使用毒药？选择目标或跳过",
                    })
                    target = parse_human_target_response(response, candidates)
                else:
                    target = await self.generate_ai_witch_poison(witch, candidates)
                
                if target and target in candidates:
                    witch.has_poison = False
                    self.night_poisoned = target
                    payload = build_witch_poison_log(witch.seat, target)
                    self.add_log(payload["type"], payload["content"], seat=payload["seat"], is_public=False, meta=payload["meta"])

        async def run_dead_ai_phantom():
            candidates = [s for s in self.get_alive_seats() if s != witch.seat]
            if self.night_kill_target:
                phantom_heal = await self.generate_ai_witch_heal(witch, self.night_kill_target)
            else:
                phantom_heal = False

            phantom_poison = await self.generate_ai_witch_poison(witch, candidates)
            self.add_phantom_action(
                "女巫",
                witch.seat,
                "witch",
                phantom_poison,
                build_witch_phantom_summary(self.night_kill_target, phantom_heal, phantom_poison),
                self.night_count,
            )

        await run_phantom_role_action(witch, (4.0, 8.0), run_live_action, run_dead_ai_phantom)

    async def resolve_night(self):
        """Resolve night actions and announce deaths"""
        deaths = []
        
        # Wolf kill (unless healed or guarded)
        if should_apply_wolf_kill(self.night_kill_target, self.night_healed, self.night_guarded):
            eliminated = await self.eliminate_player(self.night_kill_target, "wolf_kill")
            append_unique_deaths(deaths, eliminated)
        
        # Witch poison
        if self.night_poisoned:
            eliminated = await self.eliminate_player(self.night_poisoned, "poison")
            append_unique_deaths(deaths, eliminated)
        
        # Announce
        self.day_count += 1
        self.phase = GamePhase.DAY

        announcement = build_night_announcement(self.day_count, deaths)
        self.add_log(announcement["type"], announcement["content"], meta=announcement["meta"])
        
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
                response = await self.wait_for_human(seat, "speech", build_human_speech_options())
                speech = resolve_human_speech(response)
            else:
                speech = await self.generate_ai_speech(player)
            
            payload = build_speech_log(seat, speech, self.extract_speech_meta)
            self.add_log(payload["type"], payload["content"], seat=payload["seat"], meta=payload["meta"])
            await self.emit_state()
            await asyncio.sleep(0.5)  # Brief pause between speeches
        
        # Voting
        await self.run_vote()

    def build_system_prompt(self, player: Player) -> str:
        return build_ai_system_prompt(player)

    async def generate_ai_speech(self, player: Player) -> str:
        """Generate AI player speech"""
        context = self.build_context_for_player(player)
        sys_prompt = self.build_system_prompt(player)
        
        extra_info = build_extra_role_info(player)
        user_prompt = build_day_speech_user_prompt(player.seat, context, extra_info)
        messages = build_llm_messages(sys_prompt, user_prompt)
        
        response = await self.call_llm(player, messages, cache_namespace="day-speech")
        if response:
            return response

        alive_candidates = [seat for seat in sorted(self.get_alive_seats()) if seat != player.seat]
        return choose_speech_fallback(player.seat, alive_candidates)

    def build_context_for_player(self, player: Player) -> str:
        return summarize_player_context(
            player=player,
            day_count=self.day_count,
            night_count=self.night_count,
            alive_seats=self.get_alive_seats(),
            logs=self.logs,
            claim_summary=self.build_public_claim_summary(),
        )

    async def generate_ai_vote(self, player: Player, candidates: List[int], current_votes: Dict[int, int]) -> Optional[int]:
        """AI玩家投票决策 - 使用LLM"""
        context = build_vote_context(
            player=player,
            day_count=self.day_count,
            alive_seats=self.get_alive_seats(),
            candidates=candidates,
            current_votes=current_votes,
            logs=self.logs,
            claim_summary=self.build_public_claim_summary(),
        )
        
        sys_prompt = self.build_system_prompt(player)
        user_prompt = build_day_vote_user_prompt(player.seat, context)
        messages = build_llm_messages(sys_prompt, user_prompt)
        
        response = await self.call_llm(player, messages, cache_namespace="day-vote")
        target = parse_ai_vote_response(response, candidates)
        if target is not None:
            return target
        
        scores = self.build_vote_scores(player, candidates, current_votes)
        return choose_vote_fallback(candidates, scores)

    async def run_vote(self):
        """Execute voting phase - 顺序执行，每个投票后实时广播"""
        self.phase = GamePhase.VOTE
        self.add_log("phase", "开始投票环节")
        await self.emit_state()
        
        candidates = self.get_alive_seats()
        votes: Dict[int, int] = {}  # voter -> target
        last_voter_by_target: Dict[int, int] = {}
        apply_vote_rights(
            self.players,
            self.get_alive_seats(),
            self.restricted_voters_next_day,
        )
        if self.restricted_voters_next_day is not None:
            self.restricted_voters_next_day = None
        
        for seat in sorted(self.get_alive_seats()):
            player = self.players[seat]
            if not player.can_vote:
                payload = build_skipped_vote_log(seat)
                self.add_log(payload["type"], payload["content"], seat=payload["seat"], meta=payload["meta"])
                await self.emit_state()
                await asyncio.sleep(0.3)
                continue
            valid_targets = build_valid_vote_targets(candidates, seat)
            
            if player.is_human:
                response = await self.wait_for_human(seat, "vote", build_human_vote_options(valid_targets, votes))
                target = response.get("target") if response else None
            else:
                # AI投票 - 使用LLM决策，传入当前投票情况
                target = await self.generate_ai_vote(player, valid_targets, votes)
            
            if target and target in valid_targets:
                record_vote_choice(votes, last_voter_by_target, seat, target)
                payload = build_cast_vote_log(seat, target)
                self.add_log(payload["type"], payload["content"], seat=payload["seat"], meta=payload["meta"])
                # 每次投票后立即广播，让后面的玩家能看到
                await self.emit_state()
                await asyncio.sleep(0.3)  # 短暂延迟，让前端有时间显示
        
        resolution = resolve_vote_round(votes)

        if resolution:
            if not resolution.is_tie:
                eliminated = resolution.eliminated_seat
                assert eliminated is not None
                eliminated_chain = await self.eliminate_player(
                    eliminated,
                    "vote",
                    context={"last_voter": last_voter_by_target.get(eliminated)},
                )
                if eliminated_chain:
                    payload = build_vote_eliminate_log(resolution, eliminated_chain)
                else:
                    payload = build_vote_result_log(resolution)
                self.add_log(payload["type"], payload["content"], meta=payload["meta"])
            else:
                scapegoat = self.get_player_by_role(Role.SCAPEGOAT)
                if scapegoat:
                    scapegoat_seat = scapegoat.seat
                    eliminated_chain = await self.eliminate_player(
                        scapegoat_seat,
                        "scapegoat",
                        allow_hunter=False,
                        context={"tie_targets": list(resolution.top_targets)},
                    )
                    await self.scapegoat_choose_voters(scapegoat_seat)
                    payload = build_scapegoat_tie_log(resolution, scapegoat_seat, eliminated_chain)
                else:
                    payload = build_vote_tie_log(resolution)
                self.add_log(payload["type"], payload["content"], meta=payload["meta"])
        
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
        end_log, reveal_log = build_end_game_logs(self.players, winner)
        self.add_log(end_log["type"], end_log["content"])
        self.add_log(reveal_log["type"], reveal_log["content"])
        
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
            game_record = build_game_record(
                game_id=self.game_id,
                start_time=self.start_time,
                end_time=end_time,
                players=self.players,
                winner=winner,
                day_count=self.day_count,
                logs=self.logs,
                day_summary=self.build_day_summary(),
                phantom_actions=self.phantom_actions,
            )
            
            stats_manager.record_game(game_record)
            print(f"Game stats recorded: {self.game_id}")
        except Exception as e:
            print(f"Failed to record game stats: {e}")
