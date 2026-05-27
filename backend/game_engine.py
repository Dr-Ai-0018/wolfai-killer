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

from game_human import submit_human_action_response, wait_for_human_action
from game_first_night import run_cupid_action, run_wild_child_action
from game_loop import emit_initial_roles, run_game_round
from game_night_flow import execute_night_phase
from game_night_roles import run_fox_action, run_guard_action, run_seer_action, run_witch_action, run_wolf_action
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
from game_elimination import (
    apply_primary_elimination,
    resolve_hunter_chain,
    resolve_immediate_elimination,
    resolve_post_elimination_effects,
    resolve_super_saint_revenge,
)
from game_resolution import determine_winner, should_disable_powers_for_elder, awaken_wild_children
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
from game_vote_flow import collect_vote_round, resolve_vote_outcome


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
        self.total_players = 0
        self.num_wolves = 0
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
        self.total_players = total_players
        self.num_wolves = num_wolves

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

        immediate_result = await resolve_immediate_elimination(self, seat, cause)
        if immediate_result is not None:
            return immediate_result

        eliminated = apply_primary_elimination(self, seat, cause)
        await resolve_post_elimination_effects(self, eliminated)
        await resolve_super_saint_revenge(self, player, seat, cause, allow_hunter, context, eliminated)
        await resolve_hunter_chain(self, eliminated, allow_hunter)

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
        return await wait_for_human_action(self, seat, action_type, options, timeout=timeout)

    def submit_human_action(self, seat: int, action_data: Any) -> bool:
        """Submit human player action"""
        return submit_human_action_response(self, seat, action_data)

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
        self.phase = GamePhase.NIGHT
        await execute_night_phase(self)

    def get_player_by_role_any(self, role: Role) -> Optional[Player]:
        """获取某角色的玩家（无论死活）"""
        for p in self.players.values():
            if p.role == role:
                return p
        return None

    async def cupid_action(self):
        await run_cupid_action(self)

    async def wild_child_action(self):
        await run_wild_child_action(self)

    async def guard_action_with_phantom(self):
        """守卫行动 - 包含死亡角色的虚拟行动用于时间混淆"""
        await run_guard_action(self)

    async def wolf_action(self):
        """Wolves choose kill target"""
        await run_wolf_action(self)

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
        await run_fox_action(self)

    async def seer_action_with_phantom(self):
        """预言家行动 - 包含死亡角色的虚拟行动"""
        await run_seer_action(self)

    async def witch_action_with_phantom(self):
        """女巫行动 - 包含死亡角色的虚拟行动"""
        await run_witch_action(self)

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

        votes, last_voter_by_target = await collect_vote_round(self)
        await resolve_vote_outcome(self, votes, last_voter_by_target)

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
        await emit_initial_roles(self)
        
        # Main loop
        while True:
            if await run_game_round(self):
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
