import pathlib
import sys
import unittest
from datetime import datetime


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_catalog import Camp, Personality, Role
from game_end import build_end_game_logs, build_game_record
from game_engine import Player


class GameEndHelpersTests(unittest.TestCase):
    def test_build_end_game_logs_reveals_sorted_roles(self):
        players = {
            2: Player(seat=2, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
            1: Player(seat=1, role=Role.SEER, camp=Camp.GOOD, is_human=True),
        }

        end_log, reveal_log = build_end_game_logs(players, "狼人阵营")

        self.assertEqual(end_log, {"type": "end", "content": "游戏结束！狼人阵营获胜！"})
        self.assertEqual(reveal_log, {"type": "reveal", "content": "身份揭晓：1号：预言家，2号：狼人"})

    def test_build_game_record_splits_logs_and_summarizes_llm_usage(self):
        analyst = Personality(
            code="analyst",
            name="分析师",
            description="偏理性",
        )
        players = {
            1: Player(seat=1, role=Role.SEER, camp=Camp.GOOD, is_human=True, alive=False),
            2: Player(
                seat=2,
                role=Role.WOLF,
                camp=Camp.WOLF,
                is_human=False,
                model_name="gpt-5.4",
                personality=analyst,
            ),
        }
        logs = [
            {"type": "phase", "is_public": True, "content": "开始白天"},
            {"type": "llm_trace", "is_public": False, "meta": {"input_tokens": 11, "cached_tokens": 3, "output_tokens": 7}},
            {"type": "llm_trace", "is_public": False, "meta": {"input_tokens": 5, "cached_tokens": 0, "output_tokens": 2}},
        ]

        record = build_game_record(
            game_id="g-1",
            start_time=datetime(2026, 5, 27, 10, 0, 0),
            end_time=datetime(2026, 5, 27, 10, 2, 5),
            players=players,
            winner="狼人阵营",
            day_count=2,
            logs=logs,
            day_summary={"vote_counts": {2: 1}},
            phantom_actions=[{"seat": 3, "role": "预言家"}],
        )

        self.assertEqual(record["duration"], 125)
        self.assertEqual(record["num_wolves"], 1)
        self.assertEqual(record["num_humans"], 1)
        self.assertEqual(len(record["public_logs"]), 1)
        self.assertEqual(len(record["private_logs"]), 2)
        self.assertEqual(record["logs"], record["public_logs"])
        self.assertEqual(record["log_counts"], {"phase": 1, "llm_trace": 2})
        self.assertEqual(
            record["llm_usage_summary"],
            {"request_count": 2, "input_tokens": 16, "cached_tokens": 3, "output_tokens": 9},
        )
        self.assertEqual(record["players"][1]["personality_name"], "分析师")


if __name__ == "__main__":
    unittest.main()
