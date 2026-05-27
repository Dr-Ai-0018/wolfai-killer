import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_night_flow import execute_night_phase


class DummyNightPhase:
    NIGHT = "night"


class NightFlowEngineStub:
    def __init__(self):
        self.night_count = 0
        self.phase = DummyNightPhase()
        self.night_kill_target = 9
        self.night_healed = True
        self.night_poisoned = 8
        self.cupid_paired = False
        self.powers_disabled = False
        self.logs = []
        self.calls = []
        self.state_emits = 0

    def add_log(self, log_type, content, **kwargs):
        self.logs.append({"type": log_type, "content": content, **kwargs})

    async def emit_state(self):
        self.state_emits += 1

    async def announce_role_action(self, role, message, duration=None):
        self.calls.append(("announce", role, message, duration))

    async def wild_child_action(self):
        self.calls.append(("wild_child",))

    async def cupid_action(self):
        self.calls.append(("cupid",))

    async def guard_action_with_phantom(self):
        self.calls.append(("guard",))

    async def wolf_action(self):
        self.calls.append(("wolf",))

    async def fox_action_with_phantom(self):
        self.calls.append(("fox",))

    async def seer_action_with_phantom(self):
        self.calls.append(("seer",))

    async def witch_action_with_phantom(self):
        self.calls.append(("witch",))

    async def clear_role_announcement(self):
        self.calls.append(("clear",))

    async def resolve_night(self):
        self.calls.append(("resolve",))


class GameNightFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_execute_night_phase_runs_first_night_sequence(self):
        engine = NightFlowEngineStub()

        await execute_night_phase(engine)

        self.assertEqual(engine.night_count, 1)
        self.assertEqual(engine.night_kill_target, None)
        self.assertFalse(engine.night_healed)
        self.assertIsNone(engine.night_poisoned)
        self.assertEqual(engine.logs[0]["type"], "phase")
        self.assertEqual(
            [call[0] for call in engine.calls if call[0] != "announce"],
            ["wild_child", "cupid", "guard", "wolf", "fox", "seer", "witch", "clear", "resolve"],
        )

    async def test_execute_night_phase_skips_power_roles_when_disabled(self):
        engine = NightFlowEngineStub()
        engine.night_count = 1
        engine.cupid_paired = True
        engine.powers_disabled = True

        await execute_night_phase(engine)

        non_announce = [call[0] for call in engine.calls if call[0] != "announce"]
        self.assertEqual(non_announce, ["wolf", "clear", "resolve"])


if __name__ == "__main__":
    unittest.main()
