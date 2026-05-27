import pathlib
import sys
import unittest

from fastapi import HTTPException


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app_game_read import (
    get_game_log_response,
    get_game_player_view_response,
    get_game_players_response,
    get_game_status_response,
)


class DummyPhase:
    def __init__(self, value: str):
        self.value = value


class DummyPlayer:
    def __init__(self, seat: int):
        self.seat = seat

    def to_public_dict(self):
        return {"seat": self.seat, "public": True}

    def to_private_dict(self):
        return {"seat": self.seat, "private": True}


class DummyEngine:
    def __init__(self):
        self.phase = DummyPhase("waiting")
        self.day_count = 1
        self.night_count = 1
        self.paused = False
        self.winner = None
        self.waiting_for_human = None
        self.human_action_type = None
        self.human_action_options = {}
        self.players = {1: DummyPlayer(1), 2: DummyPlayer(2)}
        self.logs = [{"type": "speech", "is_public": True, "content": "hello"}]

    def get_alive_seats(self):
        return [1, 2]

    def build_day_summary(self):
        return {"claims": {}}


class DummyGameManager:
    def __init__(self, engine=None):
        self.engine = engine

    def get_game(self, _game_id: str):
        return self.engine


class AppGameReadTests(unittest.TestCase):
    def test_get_game_status_response(self):
        payload = get_game_status_response(DummyGameManager(DummyEngine()), "game-1")

        self.assertEqual(payload["game_id"], "game-1")
        self.assertEqual(payload["phase"], "waiting")

    def test_get_game_players_response(self):
        payload = get_game_players_response(DummyGameManager(DummyEngine()), "game-1")

        self.assertEqual(payload, [{"seat": 1, "public": True}, {"seat": 2, "public": True}])

    def test_get_game_player_view_response(self):
        payload = get_game_player_view_response(DummyGameManager(DummyEngine()), "game-1", 2)

        self.assertEqual(payload, {"seat": 2, "private": True})

    def test_get_game_log_response(self):
        payload = get_game_log_response(DummyGameManager(DummyEngine()), "game-1", 0, 10)

        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["logs"][0]["content"], "hello")

    def test_missing_game_or_player_still_raises_http_exception(self):
        with self.assertRaises(HTTPException):
            get_game_status_response(DummyGameManager(None), "missing")
        with self.assertRaises(HTTPException):
            get_game_player_view_response(DummyGameManager(DummyEngine()), "game-1", 9)


if __name__ == "__main__":
    unittest.main()
