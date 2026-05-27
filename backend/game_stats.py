"""
游戏统计和历史记录模块
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class GameRecord:
    """单局游戏记录"""
    game_id: str
    start_time: str
    end_time: Optional[str] = None
    duration: int = 0  # 秒
    total_players: int = 12
    num_wolves: int = 3
    num_humans: int = 0
    winner_camp: Optional[str] = None  # "好人阵营" 或 "狼人阵营"
    total_rounds: int = 0  # 天数
    players: List[Dict] = None  # 玩家信息列表
    
    def __post_init__(self):
        if self.players is None:
            self.players = []


class GameStatsManager:
    """游戏统计管理器"""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), "data")
        self.data_dir = data_dir
        self.history_file = os.path.join(data_dir, "game_history.json")
        self.stats_file = os.path.join(data_dir, "game_stats.json")
        self.reports_dir = os.path.join(data_dir, "reports")
        self.raw_games_dir = os.path.join(data_dir, "games")
        
        # 确保目录存在
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)
        os.makedirs(self.raw_games_dir, exist_ok=True)
        
        # 加载数据
        self.history: List[Dict] = self._load_history()
        self.stats: Dict = self._load_stats()
    
    def _load_history(self) -> List[Dict]:
        """加载历史记录"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"加载历史记录失败：{e}")
        return []
    
    def _load_stats(self) -> Dict:
        """加载统计数据"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"加载统计数据失败：{e}")
        return self._init_stats()
    
    def _init_stats(self) -> Dict:
        """初始化统计数据结构"""
        return {
            # 总体统计
            "total_games": 0,
            "total_rounds": 0,
            "wolf_wins": 0,
            "good_wins": 0,
            "total_duration": 0,  # 总游戏时长（秒）
            
            # 按角色统计
            "role_stats": {
                # 狼人阵营
                "狼人": {"games": 0, "wins": 0, "kills": 0, "deaths": 0},
                "狼王": {"games": 0, "wins": 0, "deaths": 0},
                "白狼王": {"games": 0, "wins": 0, "deaths": 0},
                "狼美人": {"games": 0, "wins": 0, "deaths": 0},
                # 好人阵营 - 神职
                "村民": {"games": 0, "wins": 0, "deaths": 0, "correct_votes": 0},
                "预言家": {"games": 0, "wins": 0, "deaths": 0, "checks": 0, "found_wolves": 0},
                "女巫": {"games": 0, "wins": 0, "deaths": 0, "heals": 0, "poisons": 0},
                "猎人": {"games": 0, "wins": 0, "deaths": 0, "shots": 0, "wolf_shots": 0},
                "守卫": {"games": 0, "wins": 0, "deaths": 0, "guards": 0, "successful_guards": 0},
                "狐狸": {"games": 0, "wins": 0, "deaths": 0},
                "天使": {"games": 0, "wins": 0, "deaths": 0},
                "丘比特": {"games": 0, "wins": 0, "deaths": 0},
                "白痴": {"games": 0, "wins": 0, "deaths": 0},
                "长老": {"games": 0, "wins": 0, "deaths": 0},
            },
            
            # 按人格统计
            "personality_stats": {},
            
            # 按模型统计
            "model_stats": {},
            
            # 最近更新时间
            "last_updated": None,
        }
    
    def _save_history(self):
        """保存历史记录"""
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存历史记录失败：{e}")
    
    def _save_stats(self):
        """保存统计数据"""
        try:
            self.stats["last_updated"] = datetime.now().isoformat()
            with open(self.stats_file, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存统计数据失败：{e}")
    
    def record_game(self, game_record: Dict):
        """记录一局游戏"""
        game_id = str(game_record.get("game_id") or f"game-{len(self.history) + 1}")
        try:
            raw_path = os.path.join(self.raw_games_dir, f"{game_id}.json")
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(game_record, f, ensure_ascii=False, indent=2)
            game_record["raw_record_path"] = raw_path
        except Exception as e:
            print(f"保存原始对局记录失败：{e}")

        # 添加到历史
        self.history.insert(0, game_record)  # 最新的在前面
        
        # 只保留最近1000局
        if len(self.history) > 1000:
            self.history = self.history[:1000]
        
        # 更新统计
        self._update_stats(game_record)
        
        # 保存
        self._save_history()
        self._save_stats()
    
    def _update_stats(self, game: Dict):
        """更新统计数据"""
        self.stats["total_games"] += 1
        self.stats["total_rounds"] += game.get("total_rounds", 0)
        self.stats["total_duration"] += game.get("duration", 0)
        
        winner = game.get("winner_camp", "")
        if "狼人" in winner:
            self.stats["wolf_wins"] += 1
        elif "好人" in winner:
            self.stats["good_wins"] += 1
        
        # 更新玩家相关统计
        players = game.get("players", [])
        for player in players:
            role = player.get("role", "")
            personality = player.get("personality_name", "")
            model = player.get("model_name", "")
            alive = player.get("alive", False)
            camp = player.get("camp", "")
            
            # 角色统计
            if role in self.stats["role_stats"]:
                role_stat = self.stats["role_stats"][role]
                role_stat["games"] += 1
                if not alive:
                    role_stat["deaths"] += 1
                # 判断是否获胜
                if winner and camp in winner:
                    role_stat["wins"] += 1
            
            # 人格统计
            if personality:
                if personality not in self.stats["personality_stats"]:
                    self.stats["personality_stats"][personality] = {
                        "games": 0, "wins": 0, "wolf_games": 0, "wolf_wins": 0,
                        "good_games": 0, "good_wins": 0
                    }
                p_stat = self.stats["personality_stats"][personality]
                p_stat["games"] += 1
                if "狼人" in camp:
                    p_stat["wolf_games"] += 1
                    if "狼人" in winner:
                        p_stat["wolf_wins"] += 1
                else:
                    p_stat["good_games"] += 1
                    if "好人" in winner:
                        p_stat["good_wins"] += 1
                if winner and camp in winner:
                    p_stat["wins"] += 1
            
            # 模型统计
            if model:
                if model not in self.stats["model_stats"]:
                    self.stats["model_stats"][model] = {
                        "games": 0, "wins": 0, "wolf_games": 0, "wolf_wins": 0,
                        "good_games": 0, "good_wins": 0
                    }
                m_stat = self.stats["model_stats"][model]
                m_stat["games"] += 1
                if "狼人" in camp:
                    m_stat["wolf_games"] += 1
                    if "狼人" in winner:
                        m_stat["wolf_wins"] += 1
                else:
                    m_stat["good_games"] += 1
                    if "好人" in winner:
                        m_stat["good_wins"] += 1
                if winner and camp in winner:
                    m_stat["wins"] += 1
    
    def get_overview(self) -> Dict:
        """获取总览统计"""
        total = self.stats["total_games"]
        return {
            "total_games": total,
            "total_rounds": self.stats["total_rounds"],
            "wolf_wins": self.stats["wolf_wins"],
            "good_wins": self.stats["good_wins"],
            "wolf_win_rate": self.stats["wolf_wins"] / total if total > 0 else 0,
            "good_win_rate": self.stats["good_wins"] / total if total > 0 else 0,
            "avg_duration": self.stats["total_duration"] / total if total > 0 else 0,
            "avg_rounds": self.stats["total_rounds"] / total if total > 0 else 0,
        }
    
    def get_role_stats(self) -> Dict:
        """获取角色统计"""
        result = {}
        for role, stat in self.stats["role_stats"].items():
            games = stat["games"]
            result[role] = {
                **stat,
                "win_rate": stat["wins"] / games if games > 0 else 0,
                "death_rate": stat["deaths"] / games if games > 0 else 0,
            }
        return result
    
    def get_personality_stats(self) -> Dict:
        """获取人格统计"""
        result = {}
        for name, stat in self.stats["personality_stats"].items():
            games = stat["games"]
            wolf_games = stat["wolf_games"]
            good_games = stat["good_games"]
            result[name] = {
                **stat,
                "win_rate": stat["wins"] / games if games > 0 else 0,
                "wolf_win_rate": stat["wolf_wins"] / wolf_games if wolf_games > 0 else 0,
                "good_win_rate": stat["good_wins"] / good_games if good_games > 0 else 0,
            }
        return result
    
    def get_model_stats(self) -> Dict:
        """获取模型统计"""
        result = {}
        for name, stat in self.stats["model_stats"].items():
            games = stat["games"]
            wolf_games = stat["wolf_games"]
            good_games = stat["good_games"]
            result[name] = {
                **stat,
                "win_rate": stat["wins"] / games if games > 0 else 0,
                "wolf_win_rate": stat["wolf_wins"] / wolf_games if wolf_games > 0 else 0,
                "good_win_rate": stat["good_wins"] / good_games if good_games > 0 else 0,
            }
        return result
    
    def get_history(self, page: int = 1, per_page: int = 20) -> Dict:
        """获取历史记录（分页）"""
        total = len(self.history)
        pages = (total + per_page - 1) // per_page if total > 0 else 1
        
        start = (page - 1) * per_page
        end = start + per_page
        
        return {
            "games": self.history[start:end],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }
    
    def get_detailed_stats(self) -> Dict:
        """获取详细统计数据"""
        return {
            "overview": self.get_overview(),
            "role_stats": self.get_role_stats(),
            "personality_stats": self.get_personality_stats(),
            "model_stats": self.get_model_stats(),
        }
    
    def get_game_detail(self, game_id: str) -> Optional[Dict]:
        """获取单局游戏详情"""
        for game in self.history:
            if game.get("game_id") == game_id:
                return game
        return None


# 全局实例
stats_manager = GameStatsManager()
