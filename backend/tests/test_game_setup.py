import pathlib
import random
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_catalog import Camp, Role
from game_engine import Player
from game_setup import assign_mason_peers, build_player_specs, resolve_ai_model_name


class GameSetupTests(unittest.TestCase):
    def test_resolve_ai_model_name_respects_manual_random_and_fallback_priority(self):
        self.assertEqual(
            resolve_ai_model_name(
                seat=2,
                models_pool=["gpt-a", "gpt-b"],
                random_models=False,
                seat_model_map={2: "manual-model"},
            ),
            "manual-model",
        )
        self.assertEqual(
            resolve_ai_model_name(
                seat=2,
                models_pool=["gpt-a", "gpt-b"],
                random_models=False,
                seat_model_map=None,
            ),
            "gpt-a",
        )

        random.seed(1)
        self.assertIn(
            resolve_ai_model_name(
                seat=2,
                models_pool=["gpt-a", "gpt-b"],
                random_models=True,
                seat_model_map=None,
            ),
            {"gpt-a", "gpt-b"},
        )

    def test_build_player_specs_separates_humans_from_ai_assignments(self):
        random.seed(7)
        specs = build_player_specs(
            total_players=4,
            human_seats=[1, 3],
            num_wolves=1,
            role_config={"WOLF": 1, "SEER": 1, "VILLAGER": 2},
            avatars=["a.webp", "b.webp", "c.webp", "d.webp"],
            models_pool=["gpt-a", "gpt-b"],
            random_models=False,
            seat_model_map={4: "manual-4"},
        )

        self.assertEqual(len(specs), 4)
        by_seat = {spec["seat"]: spec for spec in specs}

        self.assertTrue(by_seat[1]["is_human"])
        self.assertTrue(by_seat[3]["is_human"])
        self.assertIsNone(by_seat[1]["model_name"])
        self.assertIsNone(by_seat[1]["personality"])
        self.assertEqual(by_seat[2]["model_name"], "gpt-a")
        self.assertEqual(by_seat[4]["model_name"], "manual-4")
        self.assertIsNotNone(by_seat[2]["personality"])
        self.assertIsNotNone(by_seat[4]["personality"])
        self.assertEqual({spec["avatar"] for spec in specs}, {"a.webp", "b.webp", "c.webp", "d.webp"})

    def test_assign_mason_peers_only_links_other_masons(self):
        players = {
            1: Player(seat=1, role=Role.MASON, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.MASON, camp=Camp.GOOD, is_human=False),
            3: Player(seat=3, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
        }

        assign_mason_peers(players)

        self.assertEqual(players[1].mason_peers, [2])
        self.assertEqual(players[2].mason_peers, [1])
        self.assertEqual(players[3].mason_peers, [])
