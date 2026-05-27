import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admin_auth_routes import (
    build_admin_check_payload,
    build_admin_login_success_payload,
    build_admin_refresh_payload,
    build_admin_verify_payload,
)


class AdminAuthRoutesTests(unittest.TestCase):
    def test_build_admin_check_payload(self):
        self.assertEqual(
            build_admin_check_payload("secret"),
            {"configured": True, "message": "管理员密码已配置"},
        )
        self.assertEqual(
            build_admin_check_payload(None),
            {"configured": False, "message": "请在.env中设置WEREWOLF_ADMIN_PASSWORD"},
        )

    def test_build_admin_login_success_payload(self):
        payload = build_admin_login_success_payload({"access_token": "token", "token_type": "bearer"})

        self.assertEqual(
            payload,
            {"success": True, "message": "登录成功", "access_token": "token", "token_type": "bearer"},
        )

    def test_build_admin_refresh_payload(self):
        payload = build_admin_refresh_payload({"access_token": "token", "token_type": "bearer"})

        self.assertEqual(
            payload,
            {"success": True, "message": "登录凭证已刷新", "access_token": "token", "token_type": "bearer"},
        )

    def test_build_admin_verify_payload(self):
        payload = build_admin_verify_payload({"sub": "admin", "exp": 0})

        self.assertEqual(payload["valid"], True)
        self.assertEqual(payload["admin"], "admin")
        self.assertEqual(payload["expires_at"], "1970-01-01T00:00:00")


if __name__ == "__main__":
    unittest.main()
