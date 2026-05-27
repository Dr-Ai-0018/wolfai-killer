import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_control import build_success_response, submit_waiting_human_action


class DummyEngine:
    def __init__(self, waiting_for_human=None, submit_result=True):
        self.waiting_for_human = waiting_for_human
        self.submit_result = submit_result
        self.calls = []

    def submit_human_action(self, seat, action_data):
        self.calls.append((seat, action_data))
        return self.submit_result


class GameControlTests(unittest.TestCase):
    def test_build_success_response(self):
        self.assertEqual(build_success_response("done"), {"success": True, "message": "done"})

    def test_submit_waiting_human_action_when_waiting(self):
        engine = DummyEngine(waiting_for_human=3, submit_result=True)
        result = submit_waiting_human_action(engine, {"target": 5})

        self.assertEqual(result, {"success": True})
        self.assertEqual(engine.calls, [(3, {"target": 5})])

    def test_submit_waiting_human_action_when_not_waiting(self):
        engine = DummyEngine(waiting_for_human=None)
        result = submit_waiting_human_action(engine, {"target": 5})

        self.assertEqual(result, {"success": False, "message": "当前没有待提交的玩家操作"})
        self.assertEqual(engine.calls, [])
