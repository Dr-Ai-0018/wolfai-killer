"""
白天阶段 AI 发言与投票辅助逻辑。
"""

from __future__ import annotations

import random
import re
from typing import Any, Dict, List, Optional


DAY_SPEECH_INSTRUCTION = """现在是白天发言阶段，请你作为 {seat} 号玩家进行一段简短发言（3~6 句），
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


DAY_VOTE_INSTRUCTION = """现在进入白天投票阶段，你是 {seat} 号玩家，需要在所有仍然存活、且不是你自己的玩家中选择【一名要投票处决的目标】。

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


def build_day_speech_user_prompt(seat: int, context: str, extra_info: str) -> str:
    """构建白天发言阶段的用户 prompt。"""
    return DAY_SPEECH_INSTRUCTION.format(seat=seat, context=context, extra_info=extra_info)


def build_day_vote_user_prompt(seat: int, context: str) -> str:
    """构建白天投票阶段的用户 prompt。"""
    return DAY_VOTE_INSTRUCTION.format(seat=seat, context=context)


def parse_ai_vote_response(response: Optional[str], candidates: List[int]) -> Optional[int]:
    """从模型返回中提取合法投票目标。"""
    if not response:
        return None
    numbers = re.findall(r"\d+", response)
    for number in numbers:
        target = int(number)
        if target in candidates:
            return target
    return None


def choose_speech_fallback(seat: int, alive_candidates: List[int]) -> str:
    """为无法获得模型输出时提供保守的白天发言 fallback。"""
    fallback_target = alive_candidates[0] if alive_candidates else None
    if fallback_target is None:
        return f"我是{seat}号，信息不多，但我会继续听大家把逻辑讲清楚。"
    return (
        f"我是{seat}号，我先给一个临时压力位：{fallback_target}号。"
        " 现在信息还不够满，但我不接受只说观望不落点。"
        " 后面谁的发言更像回避判断、谁更像顺势跟票，我就继续追这个方向。"
    )


def choose_vote_fallback(
    candidates: List[int],
    scores: Dict[int, int],
    threshold: int = -50,
) -> Optional[int]:
    """在模型投票不可用时，根据启发式得分回退到一个目标。"""
    if scores:
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        top_score = ranked[0][1]
        top_targets = [seat for seat, score in ranked if score == top_score]
        if top_score > threshold:
            return random.choice(top_targets)
    return random.choice(candidates) if candidates else None


def build_llm_messages(system_prompt: str, user_prompt: str) -> List[Dict[str, Any]]:
    """统一构建 system/user 两段消息。"""
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
