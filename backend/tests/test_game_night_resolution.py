import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_engine import GameEngine, GamePhase
from game_night_resolution import append_unique_deaths, build_night_announcement, should_apply_wolf_kill


class GameNightResolutionTests(unittest.TestCase):
    def test_should_apply_wolf_kill(self):
        self.assertTrue(should_apply_wolf_kill(3, healed=False, guarded=None))
        self.assertFalse(should_apply_wolf_kill(None, healed=False, guarded=None))
        self.assertFalse(should_apply_wolf_kill(3, healed=True, guarded=None))
        self.assertFalse(should_apply_wolf_kill(3, healed=False, guarded=3))

    def test_append_unique_deaths(self):
        deaths = [4]
        append_unique_deaths(deaths, [2, 4, 5])

        self.assertEqual(deaths, [4, 2, 5])

    def test_build_night_announcement_with_deaths(self):
        payload = build_night_announcement(3, [5, 2])

        self.assertEqual(payload["type"], "death")
        self.assertEqual(payload["content"], "第3天：天亮了，昨晚2、5号死亡")
        self.assertEqual(payload["meta"], {"deaths": [2, 5]})

    def test_build_night_announcement_for_peaceful_night(self):
        payload = build_night_announcement(2, [])

        self.assertEqual(payload["type"], "phase")
        self.assertEqual(payload["content"], "第2天：天亮了，昨晚是平安夜")
        self.assertIsNone(payload["meta"])


class GameNightResolutionFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_resolve_night_skips_blocked_wolf_kill_and_announces_peaceful_night(self):
        engine = GameEngine("test-night-peace", {})
        engine.phase = GamePhase.NIGHT
        engine.day_count = 1
        engine.night_kill_target = 3
        engine.night_healed = True
        calls = []

        async def fake_eliminate_player(seat, cause, allow_hunter=True, context=None):
            calls.append((seat, cause))
            return [seat]

        engine.eliminate_player = fake_eliminate_player

        await engine.resolve_night()

        self.assertEqual(calls, [])
        self.assertEqual(engine.phase, GamePhase.DAY)
        self.assertEqual(engine.day_count, 2)
        self.assertEqual(engine.logs[-1]["type"], "phase")
        self.assertIn("平安夜", engine.logs[-1]["content"])

    async def test_resolve_night_merges_wolf_and_poison_deaths_before_announcement(self):
        engine = GameEngine("test-night-deaths", {})
        engine.phase = GamePhase.NIGHT
        engine.day_count = 1
        engine.night_kill_target = 3
        engine.night_poisoned = 5
        calls = []

        async def fake_eliminate_player(seat, cause, allow_hunter=True, context=None):
            calls.append((seat, cause))
            if cause == "wolf_kill":
                return [3, 4]
            return [4, 5]

        engine.eliminate_player = fake_eliminate_player

        await engine.resolve_night()

        self.assertEqual(calls, [(3, "wolf_kill"), (5, "poison")])
        self.assertEqual(engine.phase, GamePhase.DAY)
        self.assertEqual(engine.day_count, 2)
        self.assertEqual(engine.logs[-1]["type"], "death")
        self.assertEqual(engine.logs[-1]["meta"]["deaths"], [3, 4, 5])
        self.assertIn("3、4、5号死亡", engine.logs[-1]["content"])


if __name__ == "__main__":
    unittest.main()
