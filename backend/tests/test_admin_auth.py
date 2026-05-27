import os
import pathlib
import sys
import tempfile
import unittest

from fastapi import HTTPException


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admin_auth import create_admin_token, get_admin_password, get_jwt_secret, verify_token


class AdminAuthTests(unittest.TestCase):
    def setUp(self):
        self.original_secret = os.environ.get("WEREWOLF_JWT_SECRET")
        self.original_password = os.environ.get("WEREWOLF_ADMIN_PASSWORD")

    def tearDown(self):
        if self.original_secret is None:
            os.environ.pop("WEREWOLF_JWT_SECRET", None)
        else:
            os.environ["WEREWOLF_JWT_SECRET"] = self.original_secret

        if self.original_password is None:
            os.environ.pop("WEREWOLF_ADMIN_PASSWORD", None)
        else:
            os.environ["WEREWOLF_ADMIN_PASSWORD"] = self.original_password

    def test_get_jwt_secret_generates_and_reuses_env_secret(self):
        os.environ.pop("WEREWOLF_JWT_SECRET", None)

        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")
            first = get_jwt_secret(env_path=env_path)
            second = get_jwt_secret(env_path=env_path)

        self.assertTrue(first)
        self.assertEqual(first, second)

    def test_create_admin_token_and_verify_token_round_trip(self):
        os.environ["WEREWOLF_JWT_SECRET"] = "test-admin-secret"

        token_data = create_admin_token()
        payload = verify_token(token_data["access_token"])

        self.assertEqual(payload["sub"], "admin")
        self.assertEqual(payload["role"], "admin")
        self.assertEqual(token_data["token_type"], "bearer")

    def test_verify_token_rejects_invalid_token(self):
        os.environ["WEREWOLF_JWT_SECRET"] = "test-admin-secret"

        with self.assertRaises(HTTPException) as ctx:
            verify_token("invalid-token")

        self.assertEqual(ctx.exception.status_code, 401)

    def test_get_admin_password_reads_current_env(self):
        os.environ["WEREWOLF_ADMIN_PASSWORD"] = "admin-pass"
        self.assertEqual(get_admin_password(), "admin-pass")
