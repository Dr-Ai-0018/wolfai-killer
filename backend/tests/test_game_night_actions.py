import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_night_actions import (
    build_fox_action_log,
    build_fox_lose_power_log,
    build_fox_phantom_summary,
    build_fox_result_payload,
    build_guard_action_log,
    build_guard_phantom_summary,
    build_seer_action_log,
    build_seer_phantom_summary,
    build_seer_result_payload,
    build_witch_heal_log,
    build_witch_phantom_summary,
    build_witch_poison_log,
    build_wolf_action_log,
    parse_human_target_response,
    parse_human_witch_heal_response,
)


class GameNightActionsTests(unittest.TestCase):
    def test_parse_human_target_and_heal_responses(self):
        self.assertEqual(parse_human_target_response({"target": "3"}, [2, 3, 4]), 3)
        self.assertIsNone(parse_human_target_response({"target": "9"}, [2, 3, 4]))
        self.assertIsNone(parse_human_target_response(None, [2, 3, 4]))
        self.assertTrue(parse_human_witch_heal_response({"use_heal": True}))
        self.assertFalse(parse_human_witch_heal_response({"use_heal": False}))
        self.assertFalse(parse_human_witch_heal_response(None))

    def test_build_fox_payloads(self):
        action_payload = build_fox_action_log(1, 3, [2, 3, 4], "有狼人")
        lose_power_payload = build_fox_lose_power_log(1, 3, [2, 3, 4])

        self.assertEqual(action_payload["type"], "fox_action")
        self.assertEqual(action_payload["meta"]["checked"], [2, 3, 4])
        self.assertEqual(build_fox_result_payload(3, [2, 3, 4], "有狼人"), {"target": 3, "checked": [2, 3, 4], "result": "有狼人"})
        self.assertEqual(build_fox_phantom_summary(3), "嗅探3号周边")
        self.assertEqual(lose_power_payload["meta"]["action"], "lose_power")

    def test_build_guard_payloads(self):
        action_payload = build_guard_action_log(6, 2)

        self.assertEqual(action_payload["type"], "guard_action")
        self.assertEqual(action_payload["meta"]["action"], "guard")
        self.assertEqual(build_guard_phantom_summary(2), "守护2号")
        self.assertEqual(build_guard_phantom_summary(None), "跳过")

    def test_build_seer_payloads(self):
        action_payload = build_seer_action_log(2, 5, "狼人")

        self.assertEqual(action_payload["type"], "seer_action")
        self.assertEqual(action_payload["meta"]["result"], "狼人")
        self.assertEqual(build_seer_result_payload(5, "狼人"), {"target": 5, "result": "狼人"})
        self.assertEqual(build_seer_phantom_summary(5, "狼人"), "查验5号，结果是【狼人】")

    def test_build_witch_payloads(self):
        heal_payload = build_witch_heal_log(4, 2)
        poison_payload = build_witch_poison_log(4, 3)

        self.assertEqual(heal_payload["meta"]["action"], "heal")
        self.assertEqual(poison_payload["meta"]["action"], "poison")
        self.assertEqual(build_witch_phantom_summary(2, True, 3), "救2号；毒3号")
        self.assertEqual(build_witch_phantom_summary(2, False, None), "不救2号；不使用毒药")
        self.assertEqual(build_witch_phantom_summary(None, False, None), "不使用毒药")

    def test_build_wolf_payloads(self):
        action_payload = build_wolf_action_log(4)

        self.assertEqual(action_payload["type"], "wolf_action")
        self.assertEqual(action_payload["meta"]["action"], "kill")
        self.assertEqual(action_payload["meta"]["target"], 4)


if __name__ == "__main__":
    unittest.main()
