import pathlib
import sys
import unittest

from fastapi import HTTPException


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app_readonly import (
    build_admin_config_payload,
    build_model_catalog,
    build_stats_overview_payload,
    count_active_games,
    get_stats_game_detail_or_404,
)


class DummyPhase:
    def __init__(self, value: str):
        self.value = value


class DummyGame:
    def __init__(self, phase: str):
        self.phase = DummyPhase(phase)


class DummyStatsManager:
    def __init__(self, detail=None):
        self.detail = detail

    def get_game_detail(self, _game_id: str):
        return self.detail


class AppReadonlyTests(unittest.TestCase):
    def test_build_model_catalog_uses_normalized_ids(self):
        payload = build_model_catalog(["ignored"], lambda raw: ["gpt-5.4-mini", "gpt-5.2"])

        self.assertEqual(
            payload,
            [{"id": "gpt-5.4-mini", "label": "gpt-5.4-mini"}, {"id": "gpt-5.2", "label": "gpt-5.2"}],
        )

    def test_count_active_games_ignores_waiting_and_ended(self):
        total = count_active_games([DummyGame("waiting"), DummyGame("day"), DummyGame("vote"), DummyGame("ended")])

        self.assertEqual(total, 2)

    def test_build_stats_overview_payload_adds_active_games(self):
        payload = build_stats_overview_payload({"total_games": 5}, [DummyGame("night"), DummyGame("waiting")])

        self.assertEqual(payload, {"total_games": 5, "active_games": 1})

    def test_get_stats_game_detail_or_404(self):
        detail = get_stats_game_detail_or_404(DummyStatsManager(detail={"game_id": "g1"}), "g1")
        self.assertEqual(detail, {"game_id": "g1"})

        with self.assertRaises(HTTPException) as ctx:
            get_stats_game_detail_or_404(DummyStatsManager(detail=None), "missing")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_build_admin_config_payload_masks_key_and_duplicates_model_ids(self):
        payload = build_admin_config_payload(
            {
                "api": {
                    "base_url": "https://example.com/v1",
                    "api_key": "sk-abcdef",
                    "default_timeout": 90,
                    "model_timeout_map": {"gpt-5.4-mini": 30},
                },
                "models": ["raw"],
            },
            lambda raw: ["gpt-5.4-mini", "gpt-5.2"],
        )

        self.assertEqual(payload["api_url"], "https://example.com/v1")
        self.assertEqual(payload["api_key_masked"], "***cdef")
        self.assertEqual(payload["models"], ["gpt-5.4-mini", "gpt-5.2"])
        self.assertEqual(payload["model_ids"], ["gpt-5.4-mini", "gpt-5.2"])
        self.assertEqual(payload["default_timeout"], 90)
        self.assertEqual(payload["model_timeout_map"], {"gpt-5.4-mini": 30})


if __name__ == "__main__":
    unittest.main()
