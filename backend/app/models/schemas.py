"""
Pydantic schemas for API request/response validation
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class GameCreateRequest(BaseModel):
    """Request to create a new game"""
    player_count: int = Field(ge=6, le=12, description="Number of players")
    human_seats: List[int] = Field(default_factory=list, description="Seats for human players")
    model_name: Optional[str] = Field(None, description="Default AI model name")
    random_models: bool = Field(True, description="Randomly assign models to AI players")
    seat_model_map: Optional[Dict[int, str]] = Field(None, description="Manual model assignment per seat")
    god_mode_password: Optional[str] = Field(None, description="Password for god mode")


class ActionRequest(BaseModel):
    """Request to submit a player action"""
    action_type: str
    data: Dict[str, Any]


class AdminLoginRequest(BaseModel):
    """Admin login request"""
    password: str


class AdminConfigUpdate(BaseModel):
    """Request to update admin configuration"""
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    models: Optional[List[str]] = None


class FetchModelsRequest(BaseModel):
    """Request to fetch models from remote API"""
    api_url: str
    api_key: str


class GodModeVerifyRequest(BaseModel):
    """Request to verify god mode password"""
    password: str


class VoteInfo(BaseModel):
    """Vote information for visualization"""
    voter: int
    target: int
    
    
class SpeechBubble(BaseModel):
    """Speech bubble for display"""
    seat: int
    content: str
    timestamp: str
