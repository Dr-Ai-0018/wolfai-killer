"""
日间 AI 提示词与上下文构建辅助逻辑。
"""

from typing import Any, Dict, List

from game_catalog import Camp, Role


def build_system_prompt(player: Any) -> str:
    """构建完整的系统提示词。"""
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


def build_extra_role_info(player: Any) -> str:
    """构建玩家私有额外信息。"""
    extra_info_lines: List[str] = []
    if player.role == Role.SEER and player.seer_results:
        extra_info_lines.append(
            "你是预言家，你个人掌握的查验结果为："
            + ", ".join(f"{k}号={v}" for k, v in player.seer_results.items())
        )
    if player.role == Role.FOX:
        if player.fox_checks:
            extra_info_lines.append(
                "你是狐狸，你掌握的嗅探结果为："
                + ", ".join(f"围绕{k}号={v}" for k, v in player.fox_checks.items())
                + f"。你当前{'仍然可以' if player.fox_power_active else '已经不能再'}继续嗅探。"
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
        extra_info_lines.append(f"你是守卫，你上一夜守护了{player.guard_last_target}号。")
    if player.role == Role.MASON:
        if player.mason_peers:
            extra_info_lines.append(
                "你是共济会成员，你已知的同伴是："
                + "、".join(f"{seat}号" for seat in player.mason_peers)
                + "。"
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
    return "\n".join(extra_info_lines) or "你没有额外的隐藏信息。"


def build_context_for_player(
    *,
    player: Any,
    day_count: int,
    night_count: int,
    alive_seats: List[int],
    logs: List[Dict[str, Any]],
    claim_summary: Dict[str, List[int]],
) -> str:
    """构建日间 AI 使用的局面摘要。"""
    lines = [
        f"这是第 {day_count} 天 / 第 {night_count} 夜之后的局面。",
        f"当前存活玩家座位号：{sorted(alive_seats)}。",
    ]

    recent_deaths = [log for log in logs[-10:] if log["type"] == "death"]
    if recent_deaths:
        lines.append(f"昨夜死亡信息：{recent_deaths[-1]['content']}")

    if claim_summary:
        parts = [f"{role}：{','.join(str(seat) + '号' for seat in seats)}" for role, seats in sorted(claim_summary.items())]
        lines.append("当前公开身份声明：" + "；".join(parts))

    lines.append("")
    lines.append("最近的公开日志（发言和投票）：")

    for log in logs[-30:]:
        if log["is_public"] and log["type"] in ["speech", "vote", "eliminate"]:
            if log["type"] == "speech":
                lines.append(f"【{log['seat']}号发言】{log['content']}")
            else:
                lines.append(log["content"])

    return "\n".join(lines)


def build_vote_context(
    *,
    player: Any,
    day_count: int,
    alive_seats: List[int],
    candidates: List[int],
    current_votes: Dict[int, int],
    logs: List[Dict[str, Any]],
    claim_summary: Dict[str, List[int]],
) -> str:
    """构建投票决策上下文。"""
    context_lines = [
        f"当前是第{day_count}天投票环节",
        f"你是{player.seat}号玩家，身份是{player.role.value}",
        f"存活玩家：{', '.join(str(s) for s in sorted(alive_seats))}",
        f"可投票目标：{', '.join(str(c) for c in candidates)}",
        "",
    ]

    if current_votes:
        context_lines.append("当前已投票情况：")
        for voter, target in current_votes.items():
            context_lines.append(f"  {voter}号 -> {target}号")
        context_lines.append("")

    context_lines.append("今天的发言记录：")
    for log in logs:
        if log["is_public"] and log["type"] == "speech" and log.get("day") == day_count:
            context_lines.append(f"{log['seat']}号：{log['content']}")

    if claim_summary:
        context_lines.append("")
        context_lines.append("当前公开身份声明：")
        for role_name, seats in sorted(claim_summary.items()):
            context_lines.append(f"  {role_name} -> {', '.join(str(seat) + '号' for seat in seats)}")

    return "\n".join(context_lines)
