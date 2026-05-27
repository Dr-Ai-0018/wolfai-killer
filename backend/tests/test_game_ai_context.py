import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_catalog import Camp, PERSONALITIES, Role
from game_engine import Player
from game_ai_context import (
    build_context_for_player,
    build_extra_role_info,
    build_system_prompt,
    build_vote_context,
)


class GameAiContextTests(unittest.TestCase):
    def test_build_system_prompt_includes_role_camp_and_personality(self):
        player = Player(
            seat=3,
            role=Role.SEER,
            camp=Camp.GOOD,
            is_human=False,
            personality=PERSONALITIES[0],
        )

        prompt = build_system_prompt(player)

        self.assertIn("你是 3 号玩家", prompt)
        self.assertIn("真实身份：预言家", prompt)
        self.assertIn("阵营：好人阵营", prompt)
        self.assertIn(PERSONALITIES[0].name, prompt)

    def test_build_extra_role_info_covers_private_role_state(self):
        seer = Player(
            seat=2,
            role=Role.SEER,
            camp=Camp.GOOD,
            is_human=False,
            personality=PERSONALITIES[0],
            seer_results={5: "狼人"},
        )
        wild_child = Player(
            seat=4,
            role=Role.WILD_CHILD,
            camp=Camp.GOOD,
            is_human=False,
            personality=PERSONALITIES[1],
            idol=6,
            wild_child_awakened=True,
        )

        seer_info = build_extra_role_info(seer)
        wild_info = build_extra_role_info(wild_child)

        self.assertIn("5号=狼人", seer_info)
        self.assertIn("榜样是6号", wild_info)
        self.assertIn("现在属于狼人阵营", wild_info)

    def test_build_context_and_vote_context_include_claims_and_public_logs(self):
        player = Player(
            seat=1,
            role=Role.VILLAGER,
            camp=Camp.GOOD,
            is_human=False,
            personality=PERSONALITIES[2],
        )
        logs = [
            {"type": "death", "content": "昨夜死亡的是 4 号", "is_public": True},
            {"type": "speech", "seat": 2, "content": "我是2号，身份是预言家。", "is_public": True, "day": 1},
            {"type": "vote", "content": "2号投给3号", "is_public": True, "day": 1},
        ]
        claim_summary = {"预言家": [2]}

        context = build_context_for_player(
            player=player,
            day_count=1,
            night_count=1,
            alive_seats=[1, 2, 3],
            logs=logs,
            claim_summary=claim_summary,
        )
        vote_context = build_vote_context(
            player=player,
            day_count=1,
            alive_seats=[1, 2, 3],
            candidates=[2, 3],
            current_votes={2: 3},
            logs=logs,
            claim_summary=claim_summary,
        )

        self.assertIn("昨夜死亡的是 4 号", context)
        self.assertIn("当前公开身份声明：预言家：2号", context)
        self.assertIn("【2号发言】我是2号，身份是预言家。", context)
        self.assertIn("当前已投票情况：", vote_context)
        self.assertIn("2号 -> 3号", vote_context)
        self.assertIn("预言家 -> 2号", vote_context)
