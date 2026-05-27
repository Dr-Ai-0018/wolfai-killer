"""
运行期数据与存储路径定义。
"""

import os
from dataclasses import dataclass


def get_default_data_dir() -> str:
    """返回运行期数据目录，允许通过环境变量覆盖。"""
    env_path = os.getenv("WEREWOLF_DATA_DIR", "").strip()
    if env_path:
        return os.path.abspath(env_path)
    return os.path.join(os.path.dirname(__file__), "data")


@dataclass(frozen=True)
class GameStoragePaths:
    """统一描述统计、报告与原始对局文件位置。"""

    data_dir: str
    history_file: str
    stats_file: str
    reports_dir: str
    raw_games_dir: str


def build_storage_paths(data_dir: str | None = None) -> GameStoragePaths:
    """构建运行期存储路径集合。"""
    resolved_data_dir = os.path.abspath(data_dir or get_default_data_dir())
    return GameStoragePaths(
        data_dir=resolved_data_dir,
        history_file=os.path.join(resolved_data_dir, "game_history.json"),
        stats_file=os.path.join(resolved_data_dir, "game_stats.json"),
        reports_dir=os.path.join(resolved_data_dir, "reports"),
        raw_games_dir=os.path.join(resolved_data_dir, "games"),
    )


def ensure_storage_dirs(paths: GameStoragePaths) -> None:
    """确保运行期目录存在。"""
    os.makedirs(paths.data_dir, exist_ok=True)
    os.makedirs(paths.reports_dir, exist_ok=True)
    os.makedirs(paths.raw_games_dir, exist_ok=True)
