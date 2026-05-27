"""
夜间角色行动结果与输入解析辅助。
"""

from typing import Any, Dict, List, Optional


def parse_human_target_response(response: Optional[Dict[str, Any]], candidates: List[int]) -> Optional[int]:
    """解析真人夜间目标选择。"""
    raw_target = response.get("target") if response else None
    if raw_target is None:
        return None
    try:
        target = int(raw_target)
    except (TypeError, ValueError):
        return None
    return target if target in candidates else None


def parse_human_witch_heal_response(response: Optional[Dict[str, Any]]) -> bool:
    """解析真人女巫是否使用解药。"""
    return bool(response.get("use_heal")) if response else False


def build_fox_action_log(seat: int, target: int, checked: List[int], result: str) -> Dict[str, Any]:
    return {
        "type": "fox_action",
        "content": f"[上帝视角] 狐狸{seat}号嗅探了{target}号相邻区域，结果为【{result}】",
        "seat": seat,
        "meta": {
            "actor_role": "狐狸",
            "target": target,
            "checked": checked,
            "result": result,
            "action": "sniff",
        },
    }


def build_fox_result_payload(target: int, checked: List[int], result: str) -> Dict[str, Any]:
    return {"target": target, "checked": checked, "result": result}


def build_fox_lose_power_log(seat: int, target: int, checked: List[int]) -> Dict[str, Any]:
    return {
        "type": "fox_action",
        "content": f"[上帝视角] 狐狸{seat}号未嗅到狼人，失去了后续嗅探能力。",
        "seat": seat,
        "meta": {"actor_role": "狐狸", "target": target, "checked": checked, "action": "lose_power"},
    }


def build_fox_phantom_summary(target: int) -> str:
    return f"嗅探{target}号周边"


def build_seer_action_log(seat: int, target: int, result: str) -> Dict[str, Any]:
    return {
        "type": "seer_action",
        "content": f"[上帝视角] 预言家{seat}号查验{target}号，结果是【{result}】",
        "seat": seat,
        "meta": {"actor_role": "预言家", "target": target, "result": result, "action": "check"},
    }


def build_seer_result_payload(target: int, result: str) -> Dict[str, Any]:
    return {"target": target, "result": result}


def build_seer_phantom_summary(target: int, result: str) -> str:
    return f"查验{target}号，结果是【{result}】"


def build_witch_heal_log(seat: int, target: int) -> Dict[str, Any]:
    return {
        "type": "witch_action",
        "content": f"[上帝视角] 女巫{seat}号救了{target}号",
        "seat": seat,
        "meta": {"actor_role": "女巫", "target": target, "action": "heal"},
    }


def build_witch_poison_log(seat: int, target: int) -> Dict[str, Any]:
    return {
        "type": "witch_action",
        "content": f"[上帝视角] 女巫{seat}号毒了{target}号",
        "seat": seat,
        "meta": {"actor_role": "女巫", "target": target, "action": "poison"},
    }


def build_witch_phantom_summary(night_kill_target: Optional[int], heal: bool, poison_target: Optional[int]) -> str:
    decisions: List[str] = []
    if night_kill_target:
        decisions.append(f"{'救' if heal else '不救'}{night_kill_target}号")
    if poison_target:
        decisions.append(f"毒{poison_target}号")
    else:
        decisions.append("不使用毒药")
    return "；".join(decisions)
