"""
白天发言阶段辅助逻辑。
"""

from typing import Any, Callable, Dict, Optional


def build_human_speech_options() -> Dict[str, Any]:
    """构建真人发言时的提示参数。"""
    return {
        "message": "请发言",
        "timeout": 60,
    }


def resolve_human_speech(response: Optional[Dict[str, Any]]) -> str:
    """解析真人发言响应，缺失时回退到默认占位文本。"""
    if not response:
        return "（未发言）"
    content = response.get("content", "（未发言）")
    return str(content) if content is not None else "（未发言）"


def build_speech_log(
    seat: int,
    speech: str,
    extract_speech_meta: Callable[[str], Dict[str, Any]],
) -> Dict[str, Any]:
    """构建公开发言日志。"""
    return {
        "type": "speech",
        "content": speech,
        "seat": seat,
        "meta": extract_speech_meta(speech),
    }
