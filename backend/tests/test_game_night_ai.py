import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_catalog import Camp, PERSONALITIES, Role
from game_engine import Player
from game_night_ai import (
    build_guard_messages,
    build_recent_public_night_context,
    build_seer_messages,
    build_witch_heal_messages,
    build_witch_poison_messages,
    build_wolf_messages,
    parse_night_target_response,
    parse_witch_poison_response,
    should_use_heal_response,
    should_witch_heal_fallback,
)


class GameNightAiTests(unittest.TestCase):
    def test_build_recent_public_night_context_filters_recent_public_entries(self):
        logs = [
            {"type": "speech", "is_public": True, "seat": 2, "content": "我是2号。"},
            {"type": "vote", "is_public": True, "content": "2号投给3号"},
            {"type": "seer_action", "is_public": False, "seat": 1, "content": "private"},
        ]

        context = build_recent_public_night_context(["前缀"], logs)

        self.assertIn("前缀", context)
        self.assertIn("2号发言：我是2号。", context)
        self.assertIn("2号投给3号", context)
        self.assertNotIn("private", context)

    def test_parse_night_target_response(self):
        self.assertEqual(parse_night_target_response("我选 4 号", [2, 4, 5]), 4)
        self.assertIsNone(parse_night_target_response("选 7 号", [2, 4, 5]))
        self.assertIsNone(parse_night_target_response(None, [2, 4, 5]))

    def test_should_use_heal_and_parse_witch_poison_response(self):
        self.assertTrue(should_use_heal_response("是"))
        self.assertTrue(should_use_heal_response("救"))
        self.assertFalse(should_use_heal_response(None))

        self.assertEqual(parse_witch_poison_response("毒3号", [2, 3, 4]), 3)
        self.assertIsNone(parse_witch_poison_response("不用", [2, 3, 4]))
        self.assertIsNone(parse_witch_poison_response(None, [2, 3, 4]))

    def test_should_witch_heal_fallback(self):
        self.assertTrue(should_witch_heal_fallback(1, 2, 2, [], True))
        self.assertTrue(should_witch_heal_fallback(1, 3, 2, [3], True))
        self.assertFalse(should_witch_heal_fallback(1, 4, 2, [], True))
        self.assertTrue(should_witch_heal_fallback(1, 4, 2, [], False))
        self.assertFalse(should_witch_heal_fallback(2, 4, 2, [], False))

    def test_build_night_messages_include_role_and_context(self):
        guard = Player(seat=1, role=Role.GUARD, camp=Camp.GOOD, is_human=False, personality=PERSONALITIES[0])
        wolf = Player(seat=2, role=Role.WOLF, camp=Camp.WOLF, is_human=False, personality=PERSONALITIES[1])
        seer = Player(seat=3, role=Role.SEER, camp=Camp.GOOD, is_human=False, personality=PERSONALITIES[2], seer_results={5: "狼人"})
        witch = Player(seat=4, role=Role.WITCH, camp=Camp.GOOD, is_human=False, personality=PERSONALITIES[0])
        logs = [{"type": "speech", "is_public": True, "seat": 6, "content": "我是6号。"}]

        guard_messages = build_guard_messages(guard, 2, [1, 2, 3], [2, 3], logs)
        wolf_messages = build_wolf_messages(wolf, [wolf], 2, [1, 3, 4], logs)
        seer_messages = build_seer_messages(seer, 2, [1, 2, 4], logs)
        heal_messages = build_witch_heal_messages(witch, 2, 3, [3], logs)
        poison_messages = build_witch_poison_messages(witch, 2, [1, 2, 3], logs)

        self.assertIn("守卫", guard_messages[0]["content"])
        self.assertIn("我是6号", guard_messages[1]["content"])
        self.assertIn("狼人", wolf_messages[0]["content"])
        self.assertIn("已查验结果", seer_messages[1]["content"])
        self.assertIn("今晚3号被狼人袭击", heal_messages[1]["content"])
        self.assertIn("可毒杀目标", poison_messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
