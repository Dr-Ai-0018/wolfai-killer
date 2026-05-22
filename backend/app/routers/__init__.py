from .admin import router as admin_router
from .game import router as game_router
from .stats import router as stats_router

__all__ = ["admin_router", "game_router", "stats_router"]
