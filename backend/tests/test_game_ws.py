import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_ws import build_connected_payload, build_missing_game_payload, handle_websocket_message


class DummyPhase:
    def __init__(self, value: str):
        self.value = value


class DummyPlayer:
    def __init__(self, seat: int):
        self.seat = seat

    def to_private_dict(self):
        return {"seat": self.seat, "role": "村民"}

    def to_public_dict(self):
        return {"seat": self.seat, "alive": True}


class DummyEngine:
    def __init__(self):
        self.phase = DummyPhase("waiting")
        self.day_count = 1
        self.night_count = 0
        self.players = {1: DummyPlayer(1)}
        self.logs = [{"is_public": True, "content": "hello"}]
        self.waiting_for_human = 1
        self.human_action_type = "speech"
        self.human_action_options = {"candidates": [2, 3]}
        self.god_mode_password = "gm-pass"
        self.submitted = []

    def submit_human_action(self, seat, action_data):
        self.submitted.append((seat, action_data))
        return True


class GameWsTests(unittest.TestCase):
    def test_build_connected_payload_and_missing_game_payload(self):
        engine = DummyEngine()
        payload = build_connected_payload(engine, 1, engine.players[1])

        self.assertEqual(payload["event"], "connected")
        self.assertEqual(payload["data"]["seat"], 1)
        self.assertEqual(payload["data"]["game_state"]["waiting_for_human"], 1)
        self.assertEqual(build_missing_game_payload()["event"], "error")

    def test_handle_websocket_message_for_ping_and_action(self):
        engine = DummyEngine()

        pong = handle_websocket_message(engine, 1, {"type": "ping"})
        action = handle_websocket_message(engine, 1, {"type": "action", "data": {"content": "hi"}})
        ignored = handle_websocket_message(engine, 2, {"type": "action", "data": {"content": "skip"}})

        self.assertEqual(pong, {"event": "pong", "data": {}})
        self.assertEqual(action, {"event": "action_received", "data": {"success": True}})
        self.assertIsNone(ignored)
        self.assertEqual(engine.submitted, [(1, {"content": "hi"})])
