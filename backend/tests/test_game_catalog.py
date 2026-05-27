import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_catalog import Camp, Role, build_roles_from_config, get_role_camp, normalize_model_ids


class GameCatalogTests(unittest.TestCase):
    def test_normalize_model_ids_deduplicates_mixed_entries(self):
        models = normalize_model_ids([
            "gpt-5.4-mini",
            {"id": "gpt-5.4"},
            {"name": "gpt-5.4-mini"},
            {"model": "gpt-5.2"},
            {"value": "gpt-5.2"},
            "",
        ])

        self.assertEqual(models, ["gpt-5.4-mini", "gpt-5.4", "gpt-5.2"])

    def test_build_roles_from_config_fills_with_villagers_and_truncates(self):
        roles = build_roles_from_config(
            total_players=5,
            num_wolves=1,
            role_config={"WOLF": 1, "SEER": 1},
        )

        self.assertEqual(len(roles), 5)
        self.assertEqual(roles.count(Role.WOLF), 1)
        self.assertEqual(roles.count(Role.SEER), 1)
        self.assertEqual(roles.count(Role.VILLAGER), 3)

    def test_get_role_camp_marks_wolf_roles_as_wolf_camp(self):
        self.assertEqual(get_role_camp(Role.WOLF), Camp.WOLF)
        self.assertEqual(get_role_camp(Role.WOLF_KING), Camp.WOLF)
        self.assertEqual(get_role_camp(Role.WHITE_WOLF), Camp.WOLF)
        self.assertEqual(get_role_camp(Role.BEAUTY), Camp.WOLF)
        self.assertEqual(get_role_camp(Role.SEER), Camp.GOOD)
