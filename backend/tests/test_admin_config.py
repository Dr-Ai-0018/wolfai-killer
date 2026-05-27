import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admin_config import (
    extract_model_ids_from_payload,
    fetch_remote_model_ids,
    normalize_openai_v1_base_url,
    update_admin_config_state,
)


class AdminConfigTests(unittest.IsolatedAsyncioTestCase):
    def test_normalize_openai_v1_base_url_and_extract_model_ids(self):
        self.assertEqual(normalize_openai_v1_base_url("https://example.com"), "https://example.com/v1")
        self.assertEqual(normalize_openai_v1_base_url("https://example.com/v1"), "https://example.com/v1")

        self.assertEqual(
            extract_model_ids_from_payload({"data": [{"id": "a"}, {"id": "b"}]}),
            ["a", "b"],
        )
        self.assertEqual(
            extract_model_ids_from_payload({"data": {"data": [{"id": "a"}]}}),
            ["a"],
        )
        self.assertEqual(
            extract_model_ids_from_payload({"models": ["a", "b"]}),
            ["a", "b"],
        )

    def test_update_admin_config_state_updates_memory_and_yaml(self):
        calls = []

        def fake_set_key(path, key, value):
            calls.append((path, key, value))

        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = str(pathlib.Path(tmpdir) / ".env")
            config_path = pathlib.Path(tmpdir) / "config.yaml"
            config_path.write_text("models:\n  - old-model\n", encoding="utf-8")
            game_config = {}

            update_admin_config_state(
                game_config=game_config,
                env_path=env_path,
                config_path=str(config_path),
                api_url="https://example.com",
                api_key="sk-test",
                requested_model_ids=["m1", {"id": "m2"}, "m1"],
                normalize_model_ids=lambda raw: ["m1", "m2"],
                set_key_fn=fake_set_key,
            )

            self.assertEqual(game_config["api"]["base_url"], "https://example.com/v1")
            self.assertEqual(game_config["api"]["api_key"], "sk-test")
            self.assertEqual(game_config["models"], ["m1", "m2"])
            self.assertIn((env_path, "WEREWOLF_API_BASE_URL", "https://example.com/v1"), calls)
            self.assertIn((env_path, "WEREWOLF_API_KEY", "sk-test"), calls)
            self.assertIn("m1", config_path.read_text(encoding="utf-8"))

    async def test_fetch_remote_model_ids_uses_existing_key_and_parses_payload(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"data": [{"id": "gpt-5.4-mini"}, {"id": "gpt-5.2"}]}

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url, headers=None):
                self.url = url
                self.headers = headers
                return FakeResponse()

        model_ids = await fetch_remote_model_ids(
            api_config={"base_url": "https://example.com/v1", "api_key": "existing-key"},
            api_url="https://example.com",
            api_key="use_existing",
            async_client_cls=FakeAsyncClient,
        )

        self.assertEqual(model_ids, ["gpt-5.4-mini", "gpt-5.2"])
