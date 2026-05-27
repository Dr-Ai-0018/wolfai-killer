import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app_create import build_create_game_response, build_game_setup_kwargs, resolve_god_mode_password
from app_requests import CreateGameRequest


class DummyPhase:
    def __init__(self, value: str):
        self.value = value


class DummyPlayer:
    def __init__(self, seat: int):
        self.seat = seat

    def to_public_dict(self):
        return {"seat": self.seat}


class DummyEngine:
    def __init__(self):
        self.game_id = "game-1"
        self.phase = DummyPhase("waiting")
        self.god_mode_password = "gm-pass"
        self.players = {1: DummyPlayer(1), 2: DummyPlayer(2)}


class AppCreateTests(unittest.TestCase):
    def test_resolve_god_mode_password(self):
        request = CreateGameRequest.model_validate({"god_mode": {"enabled": True, "password": "gm-pass"}})
        disabled = CreateGameRequest.model_validate({"god_mode": {"enabled": False, "password": "gm-pass"}})

        self.assertEqual(resolve_god_mode_password(request.god_mode), "gm-pass")
        self.assertIsNone(resolve_god_mode_password(disabled.god_mode))
        self.assertIsNone(resolve_god_mode_password(None))

    def test_build_game_setup_kwargs(self):
        request = CreateGameRequest.model_validate(
            {
                "human_seats": [1],
                "total_players": 5,
                "num_wolves": 1,
                "role_config": {"WOLF": 1, "SEER": 1, "VILLAGER": 3},
                "random_models": False,
                "seat_model_map": {"1": "gpt-5.4-mini"},
            }
        )

        payload = build_game_setup_kwargs(request, ["a.webp", "b.webp"])

        self.assertEqual(
            payload,
            {
                "human_seats": [1],
                "total_players": 5,
                "num_wolves": 1,
                "role_config": {"WOLF": 1, "SEER": 1, "VILLAGER": 3},
                "avatars": ["a.webp", "b.webp"],
                "random_models": False,
                "seat_model_map": {1: "gpt-5.4-mini"},
            },
        )

    def test_build_create_game_response(self):
        payload = build_create_game_response(DummyEngine())

        self.assertEqual(
            payload,
            {
                "game_id": "game-1",
                "players": [{"seat": 1}, {"seat": 2}],
                "status": "waiting",
                "god_mode_enabled": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
