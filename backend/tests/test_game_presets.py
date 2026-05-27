import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app_requests import CreateGameRequest
from game_presets import apply_game_preset_to_request, build_game_preset_catalog, get_game_preset


class GamePresetsTests(unittest.TestCase):
    def test_build_game_preset_catalog_contains_limited_official_presets(self):
        presets = build_game_preset_catalog()

        self.assertGreaterEqual(len(presets), 2)
        self.assertLessEqual(len(presets), 3)
        self.assertIn("standard_6p", {preset["id"] for preset in presets})

    def test_get_game_preset_returns_copy(self):
        preset = get_game_preset("standard_6p")
        assert preset is not None
        preset["name"] = "changed"

        fresh = get_game_preset("standard_6p")
        self.assertEqual(fresh["name"], "标准六人局")
        self.assertIsNone(get_game_preset("missing"))

    def test_apply_game_preset_to_request_overrides_role_setup(self):
        request = CreateGameRequest.model_validate(
            {
                "preset_id": "standard_6p",
                "human_seats": [1],
                "total_players": 12,
                "num_wolves": 3,
                "role_config": {"WOLF": 3, "VILLAGER": 9},
            }
        )

        preset = get_game_preset("standard_6p")
        apply_game_preset_to_request(request, preset)

        self.assertEqual(request.total_players, 6)
        self.assertEqual(request.num_wolves, 2)
        self.assertEqual(request.role_config, {"WOLF": 2, "SEER": 1, "WITCH": 1, "GUARD": 1, "VILLAGER": 1})


if __name__ == "__main__":
    unittest.main()
