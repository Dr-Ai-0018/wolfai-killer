import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_stats import GameStatsManager
from game_storage import build_storage_paths, ensure_storage_dirs, get_default_data_dir


class GameStorageTests(unittest.TestCase):
    def test_build_storage_paths_uses_expected_runtime_layout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = build_storage_paths(tmpdir)

            self.assertEqual(paths.data_dir, os.path.abspath(tmpdir))
            self.assertEqual(paths.history_file, os.path.join(os.path.abspath(tmpdir), "game_history.json"))
            self.assertEqual(paths.stats_file, os.path.join(os.path.abspath(tmpdir), "game_stats.json"))
            self.assertEqual(paths.reports_dir, os.path.join(os.path.abspath(tmpdir), "reports"))
            self.assertEqual(paths.raw_games_dir, os.path.join(os.path.abspath(tmpdir), "games"))

    def test_ensure_storage_dirs_and_stats_manager_share_same_boundary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = build_storage_paths(tmpdir)
            ensure_storage_dirs(paths)

            self.assertTrue(os.path.isdir(paths.data_dir))
            self.assertTrue(os.path.isdir(paths.reports_dir))
            self.assertTrue(os.path.isdir(paths.raw_games_dir))

            manager = GameStatsManager(data_dir=tmpdir)
            self.assertEqual(manager.data_dir, paths.data_dir)
            self.assertEqual(manager.history_file, paths.history_file)
            self.assertEqual(manager.stats_file, paths.stats_file)

    def test_record_game_writes_raw_record_under_runtime_games_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = GameStatsManager(data_dir=tmpdir)
            record = {
                "game_id": "test-game-1",
                "duration": 12,
                "total_rounds": 1,
                "winner_camp": "好人阵营",
                "players": [],
            }

            manager.record_game(record)

            self.assertEqual(manager.history[0]["game_id"], "test-game-1")
            self.assertTrue(manager.history[0]["raw_record_path"].startswith(manager.raw_games_dir))
            self.assertTrue(os.path.exists(manager.history_file))
            self.assertTrue(os.path.exists(manager.stats_file))
            self.assertTrue(os.path.exists(os.path.join(manager.raw_games_dir, "test-game-1.json")))

    def test_default_data_dir_resolves_relative_env_path_from_backend_root(self):
        expected = str((ROOT / "data").resolve())
        with mock.patch.dict(os.environ, {"WEREWOLF_DATA_DIR": "./data"}, clear=False):
            self.assertEqual(get_default_data_dir(), expected)

    def test_build_storage_paths_resolves_relative_argument_from_backend_root(self):
        expected = str((ROOT / "tmp-runtime-data").resolve())
        paths = build_storage_paths("./tmp-runtime-data")

        self.assertEqual(paths.data_dir, expected)
        self.assertEqual(paths.reports_dir, os.path.join(expected, "reports"))
