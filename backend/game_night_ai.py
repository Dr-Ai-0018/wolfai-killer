"""
夜间 AI 决策辅助逻辑。
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional


def build_recent_public_night_context(prefix_lines: List[str], logs: Iterable[Dict[str, Any]]) -> str:
    """构建夜间决策时可见的最近公开上下文。"""
    context_lines = list(prefix_lines)
    for log in list(logs)[-30:]:
        if log.get("is_public") and log.get("type") in ["speech", "vote", "eliminate"]:
            if log.get("type") == "speech":
                context_lines.append(f"{log['seat']}号发言：{log['content']}")
            else:
                context_lines.append(str(log["content"]))
    return "\n".join(context_lines)


def build_night_llm_messages(system_prompt: str, user_prompt: str) -> List[Dict[str, Any]]:
    """统一构建夜间 AI 调用消息。"""
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def parse_night_target_response(response: Optional[str], candidates: List[int]) -> Optional[int]:
    """从夜间模型回复中提取合法座位号。"""
    if not response:
        return None
    numbers = re.findall(r"\d+", response)
    for number in numbers:
        target = int(number)
        if target in candidates:
            return target
    return None


def should_use_heal_response(response: Optional[str]) -> bool:
    """解析女巫是否决定使用解药。"""
    if not response:
        return False
    return "是" in response or "救" in response or "yes" in response.lower()


def parse_witch_poison_response(response: Optional[str], candidates: List[int]) -> Optional[int]:
    """解析女巫是否决定用毒以及目标。"""
    if not response:
        return None
    lowered = response.lower()
    if "不" in response or "跳" in response or "no" in lowered:
        return None
    return parse_night_target_response(response, candidates)


def should_witch_heal_fallback(
    night_count: int,
    victim: int,
    witch_seat: int,
    sole_seer_claim: List[int],
    small_lobby_single_wolf: bool,
) -> bool:
    """在模型无回复时决定女巫是否默认使用解药。"""
    if small_lobby_single_wolf:
        if victim == witch_seat:
            return True
        if sole_seer_claim and victim in sole_seer_claim:
            return True
        return False
    return night_count == 1


def build_guard_messages(guard: Any, night_count: int, alive_seats: List[int], candidates: List[int], logs: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    user_prompt = build_recent_public_night_context(
        [
            f"当前是第{night_count}夜",
            f"你是{guard.seat}号守卫",
            f"存活玩家：{', '.join(str(seat) for seat in sorted(alive_seats))}",
            f"可守护目标：{', '.join(str(candidate) for candidate in candidates)}",
            "",
            "昨天的发言和投票情况：",
        ],
        logs,
    )
    system_prompt = f"""你是狼人杀游戏中的守卫，座位号{guard.seat}。
你的性格是：{guard.personality.name} - {guard.personality.description}

现在是夜晚，你需要选择一个玩家守护。被守护的玩家今晚不会被狼人杀死。
分析场上局势，选择你认为最可能被狼人袭击的重要玩家守护。

请直接回复一个数字，表示你要守护的座位号。只回复数字。"""
    return build_night_llm_messages(system_prompt, user_prompt)


def build_wolf_messages(leader: Any, wolves: List[Any], night_count: int, candidates: List[int], logs: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    wolf_seats = [wolf.seat for wolf in wolves]
    user_prompt = build_recent_public_night_context(
        [
            f"当前是第{night_count}夜",
            f"你是{leader.seat}号狼人",
            f"你的狼队友：{', '.join(str(seat) for seat in wolf_seats if seat != leader.seat) or '无'}",
            f"存活的好人：{', '.join(str(candidate) for candidate in candidates)}",
            "",
            "昨天的发言和投票情况：",
        ],
        logs,
    )
    system_prompt = f"""你是狼人杀游戏中的狼人，座位号{leader.seat}。
你的性格是：{leader.personality.name} - {leader.personality.description}

现在是夜晚，狼人需要选择一个好人击杀。
分析场上局势，优先击杀对狼人威胁最大的玩家（如预言家、女巫等神职）。

请直接回复一个数字，表示你们要击杀的座位号。只回复数字。"""
    return build_night_llm_messages(system_prompt, user_prompt)


def build_seer_messages(seer: Any, night_count: int, candidates: List[int], logs: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    user_prompt = build_recent_public_night_context(
        [
            f"当前是第{night_count}夜",
            f"你是{seer.seat}号预言家",
            f"已查验结果：{seer.seer_results if seer.seer_results else '无'}",
            f"可查验目标：{', '.join(str(candidate) for candidate in candidates)}",
            "",
            "昨天的发言和投票情况：",
        ],
        logs,
    )
    system_prompt = f"""你是狼人杀游戏中的预言家，座位号{seer.seat}。
你的性格是：{seer.personality.name} - {seer.personality.description}

现在是夜晚，你需要选择一个玩家查验其身份（狼人或好人）。
分析场上局势，选择你最怀疑或最需要确认身份的玩家。

请直接回复一个数字，表示你要查验的座位号。只回复数字。"""
    return build_night_llm_messages(system_prompt, user_prompt)


def build_witch_heal_messages(witch: Any, night_count: int, victim: int, sole_seer_claim: List[int], logs: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    user_prompt = build_recent_public_night_context(
        [
            f"当前是第{night_count}夜",
            f"你是{witch.seat}号女巫",
            f"今晚{victim}号被狼人袭击",
            f"你还有解药：{'是' if witch.has_heal else '否'}",
            f"你还有毒药：{'是' if witch.has_poison else '否'}",
            f"当前公开预言家声明：{sole_seer_claim if sole_seer_claim else '无'}",
            "",
            "昨天的发言和投票情况：",
        ],
        logs,
    )
    system_prompt = f"""你是狼人杀游戏中的女巫，座位号{witch.seat}。
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

请回复"是"或"否"，表示是否使用解药。只回复一个字。"""
    return build_night_llm_messages(system_prompt, user_prompt)


def build_witch_poison_messages(witch: Any, night_count: int, candidates: List[int], logs: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    user_prompt = build_recent_public_night_context(
        [
            f"当前是第{night_count}夜",
            f"你是{witch.seat}号女巫",
            f"可毒杀目标：{', '.join(str(candidate) for candidate in candidates)}",
            "",
            "昨天的发言和投票情况：",
        ],
        logs,
    )
    system_prompt = f"""你是狼人杀游戏中的女巫，座位号{witch.seat}。
你的性格是：{witch.personality.name} - {witch.personality.description}

你可以选择使用毒药毒死一个玩家，或者不使用。
毒药只有一瓶，用完就没有了。

考虑因素：
- 是否有明确的狼人目标
- 毒错好人的风险
- 通常建议在有把握时再用毒

如果要使用毒药，请回复要毒的座位号数字。
如果不使用毒药，请回复"不用"或"跳过"。"""
    return build_night_llm_messages(system_prompt, user_prompt)
