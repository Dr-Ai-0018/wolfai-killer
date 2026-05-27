import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_loop import emit_initial_roles, run_game_round


class DummyLoopPlayer:
    def __init__(self, seat):
        self.seat = seat

    def to_private_dict(self):
        return {"seat": self.seat, "role": "村民"}


class LoopEngineStub:
    def __init__(self):
        self.players = {}
        self.paused = False
        self.night_runs = 0
        self.day_runs = 0
        self.emits = []
        self.end_calls = []
        self._winner_sequence = []

    async def emit(self, event, data, to_seat=None):
        self.emits.append({"event": event, "data": data, "to_seat": to_seat})

    async def run_night(self):
        self.night_runs += 1

    async def run_day(self):
        self.day_runs += 1

    def check_winner(self):
        if self._winner_sequence:
            return self._winner_sequence.pop(0)
        return None

    async def end_game(self, winner):
        self.end_calls.append(winner)


class GameLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_emit_initial_roles_sends_private_role_to_each_seat(self):
        engine = LoopEngineStub()
        engine.players = {
            1: DummyLoopPlayer(1),
            2: DummyLoopPlayer(2),
        }

        await emit_initial_roles(engine)

        self.assertEqual(len(engine.emits), 2)
        self.assertEqual(engine.emits[0]["event"], "your_role")
        self.assertEqual(engine.emits[1]["to_seat"], 2)

    async def test_run_game_round_stops_after_night_winner(self):
        engine = LoopEngineStub()
        engine._winner_sequence = ["狼人阵营"]

        ended = await run_game_round(engine)

        self.assertTrue(ended)
        self.assertEqual(engine.night_runs, 1)
        self.assertEqual(engine.day_runs, 0)
        self.assertEqual(engine.end_calls, ["狼人阵营"])

    async def test_run_game_round_runs_day_when_no_night_winner(self):
        engine = LoopEngineStub()
        engine._winner_sequence = [None, "好人阵营"]

        ended = await run_game_round(engine)

        self.assertTrue(ended)
        self.assertEqual(engine.night_runs, 1)
        self.assertEqual(engine.day_runs, 1)
        self.assertEqual(engine.end_calls, ["好人阵营"])

    async def test_run_game_round_continues_when_no_winner(self):
        engine = LoopEngineStub()
        engine._winner_sequence = [None, None]

        ended = await run_game_round(engine)

        self.assertFalse(ended)
        self.assertEqual(engine.night_runs, 1)
        self.assertEqual(engine.day_runs, 1)
        self.assertEqual(engine.end_calls, [])


if __name__ == "__main__":
    unittest.main()
