"""
管理员配置写盘与模型拉取辅助逻辑。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import httpx
import yaml


def normalize_openai_v1_base_url(api_url: str) -> str:
    """接受 root URL 或 /v1 URL，并统一成 /v1 base。"""
    normalized = (api_url or "").strip().rstrip("/")
    if not normalized:
        return normalized
    return normalized if normalized.endswith("/v1") else f"{normalized}/v1"


def update_admin_config_state(
    *,
    game_config: Dict[str, Any],
    env_path: str,
    config_path: str,
    api_url: Optional[str],
    api_key: Optional[str],
    requested_model_ids: Optional[List[str]],
    normalize_model_ids: Callable[[Any], List[str]],
    set_key_fn: Callable[[str, str, str], Any],
) -> None:
    """同步更新内存配置、.env 与 config.yaml。"""
    if api_url:
        normalized_api_url = normalize_openai_v1_base_url(api_url)
        set_key_fn(env_path, "WEREWOLF_API_BASE_URL", normalized_api_url)
        if "api" not in game_config:
            game_config["api"] = {}
        game_config["api"]["base_url"] = normalized_api_url

    if api_key:
        set_key_fn(env_path, "WEREWOLF_API_KEY", api_key)
        if "api" not in game_config:
            game_config["api"] = {}
        game_config["api"]["api_key"] = api_key

    if requested_model_ids is not None:
        model_ids = normalize_model_ids(requested_model_ids)
        game_config["models"] = model_ids
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                yaml_config = yaml.safe_load(f) or {}
            yaml_config["models"] = model_ids
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(yaml_config, f, allow_unicode=True, default_flow_style=False)
        except Exception as e:
            print(f"更新配置文件失败：{e}")


def extract_model_ids_from_payload(data: Any) -> List[str]:
    """从兼容 OpenAI 风格或自定义 payload 中提取模型 ID。"""
    models_array: List[Any] = []
    if isinstance(data, dict):
        if "data" in data:
            inner_data = data["data"]
            if isinstance(inner_data, dict) and "data" in inner_data and isinstance(inner_data["data"], list):
                models_array = inner_data["data"]
            elif isinstance(inner_data, list):
                models_array = inner_data
        elif isinstance(data.get("models"), list):
            models_array = data["models"]
    elif isinstance(data, list):
        models_array = data

    model_ids: List[str] = []
    for model in models_array:
        if isinstance(model, dict) and "id" in model:
            model_ids.append(model["id"])
        elif isinstance(model, str):
            model_ids.append(model)
    return model_ids


async def fetch_remote_model_ids(
    *,
    api_config: Dict[str, Any],
    api_url: str,
    api_key: str,
    async_client_cls: type[httpx.AsyncClient],
) -> List[str]:
    """从远程接口拉取并解析模型 ID。"""
    resolved_api_url = api_url.strip() if api_url else api_config.get("base_url", "")
    resolved_api_key = api_key.strip() if api_key else ""
    if resolved_api_key == "use_existing":
        resolved_api_key = api_config.get("api_key", "")

    if not resolved_api_url:
        raise ValueError("API 地址不能为空")
    if not resolved_api_key:
        raise ValueError("API Key 未配置")

    models_url = normalize_openai_v1_base_url(resolved_api_url) + "/models"
    async with async_client_cls(timeout=30) as client:
        resp = await client.get(
            models_url,
            headers={
                "Authorization": f"Bearer {resolved_api_key}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    return extract_model_ids_from_payload(data)
