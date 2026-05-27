import pathlib
import sys
import unittest

from fastapi import HTTPException


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app_requests import (
    AdminConfigUpdate,
    CreateGameRequest,
    FetchModelsRequest,
    GodModeConfig,
    validate_role_balance,
)


class AppRequestsTests(unittest.TestCase):
    def test_create_game_request_accepts_god_mode_and_string_seat_keys(self):
        request = CreateGameRequest.model_validate(
            {
                "human_seats": [1],
                "total_players": 5,
                "num_wolves": 1,
                "random_models": False,
                "seat_model_map": {"1": "gpt-5.4-mini"},
                "god_mode": {"enabled": True, "password": "gm-pass"},
            }
        )

        self.assertEqual(request.human_seats, [1])
        self.assertEqual(request.seat_model_map, {1: "gpt-5.4-mini"})
        self.assertIsInstance(request.god_mode, GodModeConfig)
        self.assertTrue(request.god_mode.enabled)

    def test_admin_config_update_accepts_model_alias_fields(self):
        request = AdminConfigUpdate.model_validate({"models": ["gpt-5.4-mini"], "model_ids": ["gpt-5.2"]})

        self.assertEqual(request.models, ["gpt-5.4-mini"])
        self.assertEqual(request.model_ids, ["gpt-5.2"])

    def test_fetch_models_request_requires_url_and_key(self):
        request = FetchModelsRequest.model_validate({"api_url": "https://example.com", "api_key": "sk-test"})

        self.assertEqual(request.api_url, "https://example.com")
        self.assertEqual(request.api_key, "sk-test")

    def test_validate_role_balance_rejects_total_role_mismatch(self):
        with self.assertRaises(HTTPException) as ctx:
            validate_role_balance(5, {"WOLF": 1, "SEER": 1, "VILLAGER": 1}, 1)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "角色数量必须与总人数一致")

    def test_validate_role_balance_rejects_missing_wolf(self):
        with self.assertRaises(HTTPException) as ctx:
            validate_role_balance(5, {"SEER": 1, "WITCH": 1, "HUNTER": 1, "VILLAGER": 2}, 0)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "至少需要 1 个狼人阵营角色")

    def test_validate_role_balance_rejects_too_many_wolves(self):
        with self.assertRaises(HTTPException) as ctx:
            validate_role_balance(5, {"WOLF": 2, "WOLF_KING": 1, "VILLAGER": 2}, 3)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("最多允许", ctx.exception.detail)

    def test_validate_role_balance_allows_reasonable_configuration(self):
        validate_role_balance(6, {"WOLF": 1, "SEER": 1, "WITCH": 1, "VILLAGER": 3}, 1)


if __name__ == "__main__":
    unittest.main()
