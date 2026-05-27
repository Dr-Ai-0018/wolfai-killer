"""
已抽离的路由集合。

当前仅 admin 路由在 backend/app 骨架中完成模块化。
game 与 stats 仍由 backend/app.py 直接提供，尚未迁入此目录。
"""

from .admin import router as admin_router

__all__ = ["admin_router"]
