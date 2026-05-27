import pathlib
import sys
import unittest

from fastapi import HTTPException


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_views import (
    build_game_status_payload,
    build_phantom_actions_payload,
    build_public_logs_payload,
    get_engine_or_404,
    get_player_or_404,
    verify_god_mode_access,
)


class DummyPhase:
    def __init__(self, value: str):
        self.value = value


class DummyPlayer:
    def __init__(self, seat: int):
        self.seat = seat

    def to_private_dict(self):
        return {"seat": self.seat}


class DummyEngine:
    def __init__(self):
        self.phase = DummyPhase("waiting")
        self.day_count = 1
        self.night_count = 1
        self.paused = False
        self.winner = None
        self.waiting_for_human = 2
        self.human_action_type = "speech"
        self.human_action_options = {"candidates": [1, 2]}
        self.logs = [{"type": "speech", "is_public": True, "content": "hello"}]
        self.phantom_actions = [{"seat": 3}]
        self.players = {1: DummyPlayer(1)}
        self.god_mode_password = "gm-pass"

    def get_alive_seats(self):
        return [1, 2]

    def build_day_summary(self):
        return {"claims": {}}


class DummyGameManager:
    def __init__(self, engine=None):
        self.engine = engine

    def get_game(self, game_id: str):
        return self.engine


class GameViewsTests(unittest.TestCase):
    def test_getters_raise_404_when_missing(self):
        with self.assertRaises(HTTPException) as ctx:
            get_engine_or_404(DummyGameManager(engine=None), "missing")
        self.assertEqual(ctx.exception.status_code, 404)

        with self.assertRaises(HTTPException) as ctx:
            get_player_or_404(DummyEngine(), 9)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_verify_god_mode_access_and_build_payloads(self):
        engine = DummyEngine()
        verify_god_mode_access(engine, "gm-pass")

        status = build_game_status_payload(engine, "game-1")
        logs = build_public_logs_payload(engine, 0, 10)
        phantom_waiting = build_phantom_actions_payload(engine)

        self.assertEqual(status["phase"], "waiting")
        self.assertEqual(logs["total"], 1)
        self.assertFalse(phantom_waiting["available"])

        engine.phase = DummyPhase("ended")
        phantom_done = build_phantom_actions_payload(engine)
        self.assertTrue(phantom_done["available"])
        self.assertEqual(phantom_done["total"], 1)

    def test_verify_god_mode_access_rejects_missing_or_wrong_password(self):
        engine = DummyEngine()
        engine.god_mode_password = None
        with self.assertRaises(HTTPException) as ctx:
            verify_god_mode_access(engine, "gm-pass")
        self.assertEqual(ctx.exception.status_code, 403)

        engine.god_mode_password = "gm-pass"
        with self.assertRaises(HTTPException) as ctx:
            verify_god_mode_access(engine, "wrong")
        self.assertEqual(ctx.exception.status_code, 403)
