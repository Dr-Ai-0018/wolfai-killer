import pathlib
import sys
import unittest

import httpx


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admin_routes import (
    build_admin_config_updated_response,
    build_fetch_models_error_response,
    build_fetch_models_success_response,
    build_god_mode_verify_response,
)


class AdminRoutesTests(unittest.TestCase):
    def test_build_admin_config_updated_response(self):
        self.assertEqual(build_admin_config_updated_response(), {"success": True, "message": "配置已更新"})

    def test_build_fetch_models_success_response(self):
        payload = build_fetch_models_success_response(["gpt-5.4-mini", "gpt-5.2"])

        self.assertTrue(payload["success"])
        self.assertEqual(payload["models"], ["gpt-5.4-mini", "gpt-5.2"])
        self.assertEqual(payload["model_ids"], ["gpt-5.4-mini", "gpt-5.2"])
        self.assertEqual(payload["total"], 2)

    def test_build_fetch_models_error_response_for_value_error(self):
        payload = build_fetch_models_error_response(ValueError("bad config"))

        self.assertEqual(payload, {"success": False, "message": "bad config"})

    def test_build_fetch_models_error_response_for_http_status_error(self):
        request = httpx.Request("GET", "https://example.com/v1/models")
        response = httpx.Response(status_code=401, request=request, text="unauthorized-body")
        error = httpx.HTTPStatusError("boom", request=request, response=response)

        payload = build_fetch_models_error_response(error)

        self.assertEqual(payload, {"success": False, "message": "HTTP 401: unauthorized-body"})

    def test_build_god_mode_verify_response(self):
        self.assertEqual(
            build_god_mode_verify_response("pass", None),
            {"success": False, "message": "本局游戏未启用上帝模式"},
        )
        self.assertEqual(
            build_god_mode_verify_response("pass", "pass"),
            {"success": True, "message": "验证成功"},
        )
        self.assertEqual(
            build_god_mode_verify_response("wrong", "pass"),
            {"success": False, "message": "密码错误"},
        )


if __name__ == "__main__":
    unittest.main()
