"""
Configuration management - centralized settings
"""
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from functools import lru_cache

import yaml
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env file
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment and config files"""
    
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    
    # API Settings
    API_KEY: str = os.getenv("WEREWOLF_API_KEY", "")
    API_BASE_URL: str = os.getenv("WEREWOLF_API_BASE_URL", "https://api.openai.com/v1")
    
    # Admin Settings
    ADMIN_PASSWORD: str = os.getenv("WEREWOLF_ADMIN_PASSWORD", "")
    
    # Redis (optional)
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL")
    
    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/game_stats.json")
    
    # Timeouts
    DEFAULT_TIMEOUT: int = 60
    MODEL_TIMEOUT_MAP: Dict[str, int] = {}
    
    # Models
    MODELS: List[str] = []
    
    class Config:
        env_file = ".env"
        extra = "allow"
    
    def load_yaml_config(self) -> Dict[str, Any]:
        """Load additional config from YAML file"""
        config_path = self.BASE_DIR / "config.yaml"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"加载 config.yaml 失败：{e}")
            return {}
    
    def update_from_yaml(self):
        """Update settings from YAML config"""
        yaml_config = self.load_yaml_config()
        
        # API settings from YAML (env takes precedence)
        api_config = yaml_config.get("api", {})
        if not self.API_KEY:
            self.API_KEY = api_config.get("api_key", "")
        if self.API_BASE_URL == "https://api.openai.com/v1":
            self.API_BASE_URL = api_config.get("base_url", self.API_BASE_URL)
        
        self.DEFAULT_TIMEOUT = api_config.get("default_timeout", 60)
        self.MODEL_TIMEOUT_MAP = api_config.get("model_timeout_map", {})
        
        # Models
        self.MODELS = yaml_config.get("models", [])
    
    def save_to_yaml(self, updates: Dict[str, Any]):
        """Save updates to YAML config file"""
        config_path = self.BASE_DIR / "config.yaml"
        try:
            yaml_config = self.load_yaml_config()
            
            # Deep merge updates
            for key, value in updates.items():
                if key == "models":
                    yaml_config["models"] = value
                elif key in ["api_key", "base_url", "default_timeout", "model_timeout_map"]:
                    if "api" not in yaml_config:
                        yaml_config["api"] = {}
                    yaml_config["api"][key] = value
            
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(yaml_config, f, allow_unicode=True, default_flow_style=False)
            
            return True
        except Exception as e:
            print(f"保存 config.yaml 失败：{e}")
            return False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    settings = Settings()
    settings.update_from_yaml()
    return settings


# Global settings instance
settings = get_settings()
