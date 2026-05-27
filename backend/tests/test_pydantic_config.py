import pathlib
import sys
import unittest
import warnings
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import Settings
from app.models.schemas import GameCreateRequest


class PydanticConfigTests(unittest.TestCase):
    def test_settings_initialization_avoids_deprecated_class_config_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            Settings()

        messages = [str(item.message) for item in caught]
        self.assertFalse(any("class-based `config` is deprecated" in message for message in messages))

    def test_game_create_request_allows_model_name_without_namespace_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            payload = GameCreateRequest(
                player_count=6,
                human_seats=[1],
                model_name="gpt-5.4-mini",
                random_models=False,
                seat_model_map={2: "gpt-5.4-mini"},
            )

        self.assertEqual(payload.model_name, "gpt-5.4-mini")
        messages = [str(item.message) for item in caught]
        self.assertFalse(any('Field "model_name" has conflict with protected namespace "model_".' in message for message in messages))

    def test_settings_data_dir_defaults_to_backend_data_directory(self):
        expected = str((ROOT / "data").resolve())
        with mock.patch.dict("os.environ", {}, clear=True):
            settings = Settings()

        self.assertEqual(settings.DATA_DIR, expected)
