"""
app.py 请求模型与角色配置校验辅助。
"""

from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict


class GodModeConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    enabled: bool = False
    password: str = ""


class CreateGameRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    preset_id: Optional[str] = None
    human_seats: List[int] = []
    total_players: int = 12
    num_wolves: int = 3
    role_config: Optional[Dict[str, int]] = None
    random_models: bool = True
    seat_model_map: Optional[Dict[int, str]] = None
    god_mode: Optional[GodModeConfig] = None


class ActionRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    action_type: str
    data: Dict[str, Any] = {}


class GodModeVerifyRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    password: str


class AdminConfigUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    models: Optional[List[str]] = None
    model_ids: Optional[List[str]] = None


class FetchModelsRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    api_url: str
    api_key: str


class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    password: str


def validate_role_balance(total_players: int, role_config: Optional[Dict[str, int]], num_wolves: int) -> None:
    """校验角色总数与狼人阵营数量是否合理。"""
    wolf_role_codes = {"WOLF", "WOLF_KING", "WHITE_WOLF", "BEAUTY"}
    configured_wolves = num_wolves

    if role_config:
        configured_wolves = sum(int(role_config.get(code, 0) or 0) for code in wolf_role_codes)
        total_roles = sum(int(count or 0) for count in role_config.values())
        if total_roles != total_players:
            raise HTTPException(status_code=400, detail="角色数量必须与总人数一致")

    if configured_wolves < 1:
        raise HTTPException(status_code=400, detail="至少需要 1 个狼人阵营角色")

    max_wolves = max(1, (total_players - 1) // 3)
    if configured_wolves > max_wolves:
        raise HTTPException(
            status_code=400,
            detail=f"当前 {total_players} 人局最多允许 {max_wolves} 个狼人阵营角色，避免出现人数过快持平的失衡配置",
        )
