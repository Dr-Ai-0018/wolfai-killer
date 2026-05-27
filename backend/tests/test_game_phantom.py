import asyncio
import pathlib
import sys
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_phantom import pick_random_candidate, run_phantom_role_action


class DummyRolePlayer:
    def __init__(self, alive: bool, is_human: bool):
        self.alive = alive
        self.is_human = is_human


class GamePhantomTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_phantom_role_action_handles_missing_live_dead_ai_and_dead_human(self):
        calls: list[str] = []

        async def live_action():
            calls.append("live")

        async def dead_ai_action():
            calls.append("dead_ai")

        async def fake_sleep(*_args, **_kwargs):
            return None

        with patch("game_phantom.asyncio.sleep", side_effect=fake_sleep):
            exists = await run_phantom_role_action(None, (1.0, 2.0), live_action, dead_ai_action)
            self.assertFalse(exists)
            self.assertEqual(calls, [])

            exists = await run_phantom_role_action(DummyRolePlayer(alive=True, is_human=False), (1.0, 2.0), live_action, dead_ai_action)
            self.assertTrue(exists)
            self.assertEqual(calls, ["live"])

            exists = await run_phantom_role_action(DummyRolePlayer(alive=False, is_human=False), (1.0, 2.0), live_action, dead_ai_action)
            self.assertTrue(exists)
            self.assertEqual(calls, ["live", "dead_ai"])

            exists = await run_phantom_role_action(DummyRolePlayer(alive=False, is_human=True), (1.0, 2.0), live_action, dead_ai_action)
            self.assertTrue(exists)
            self.assertEqual(calls, ["live", "dead_ai"])

    def test_pick_random_candidate_returns_none_for_empty_candidates(self):
        self.assertIsNone(pick_random_candidate([]))

    async def test_run_phantom_role_action_can_execute_dead_ai_side_effects(self):
        state = {"summary": None}

        async def live_action():
            state["summary"] = "live"

        async def dead_ai_action():
            state["summary"] = "heal;poison"

        exists = await run_phantom_role_action(
            DummyRolePlayer(alive=False, is_human=False),
            (1.0, 2.0),
            live_action,
            dead_ai_action,
        )

        self.assertTrue(exists)
        self.assertEqual(state["summary"], "heal;poison")
