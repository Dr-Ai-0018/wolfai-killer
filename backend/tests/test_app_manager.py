import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app_manager import (
    GameManager,
    list_avatar_files,
    load_game_manager_config,
    normalize_model_ids,
    parse_model_timeout_overrides,
)


class AppManagerTests(unittest.IsolatedAsyncioTestCase):
    def test_normalize_model_ids_and_timeout_overrides(self):
        self.assertEqual(
            normalize_model_ids([" gpt-5.4 ", {"id": "gpt-5.4-mini"}, {"name": "gpt-5.4"}]),
            ["gpt-5.4", "gpt-5.4-mini"],
        )
        self.assertEqual(
            parse_model_timeout_overrides("gpt-5.4-mini=15,gpt-5.4=20,broken"),
            {"gpt-5.4-mini": 15, "gpt-5.4": 20},
        )

    def test_load_game_manager_config_applies_env_overrides(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = pathlib.Path(tmpdir) / "config.yaml"
            config_path.write_text(
                "api:\n  base_url: https://old.example/v1\nmodels:\n  - base-model\n",
                encoding="utf-8",
            )
            with mock.patch.dict(
                "os.environ",
                {
                    "WEREWOLF_API_BASE_URL": "https://new.example/v1",
                    "WEREWOLF_API_DEFAULT_TIMEOUT": "42",
                    "WEREWOLF_API_MODEL_TIMEOUTS": "gpt-5.4=18",
                },
                clear=False,
            ):
                config = load_game_manager_config(tmpdir)

            self.assertEqual(config["api"]["base_url"], "https://new.example/v1")
            self.assertEqual(config["api"]["default_timeout"], 42)
            self.assertEqual(config["api"]["model_timeout_map"], {"gpt-5.4": 18})
            self.assertEqual(config["models"], ["base-model"])

    def test_list_avatar_files_filters_webp_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            emojis_dir = pathlib.Path(tmpdir) / "Emojis"
            emojis_dir.mkdir()
            (emojis_dir / "a.webp").write_text("", encoding="utf-8")
            (emojis_dir / "b.png").write_text("", encoding="utf-8")

            self.assertEqual(list_avatar_files(tmpdir), ["a.webp"])

    async def test_game_manager_broadcast_to_specific_seat_and_all(self):
        class DummyWs:
            def __init__(self):
                self.messages = []

            async def send_text(self, message):
                self.messages.append(json.loads(message))

        manager = GameManager(str(ROOT))
        manager.connections["game-1"] = {1: DummyWs(), 2: DummyWs()}

        await manager.broadcast_to_game("game-1", "state", {"phase": "day"}, to_seat=1)
        await manager.broadcast_to_game("game-1", "ping", {"ok": True})

        self.assertEqual(manager.connections["game-1"][1].messages[0]["event"], "state")
        self.assertEqual(len(manager.connections["game-1"][1].messages), 2)
        self.assertEqual(len(manager.connections["game-1"][2].messages), 1)


if __name__ == "__main__":
    unittest.main()
