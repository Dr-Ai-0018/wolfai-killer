import pathlib
import random
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_catalog import Camp, Role
from game_engine import Player
from game_special_roles import (
    apply_cupid_pair,
    apply_wild_child_idol,
    choose_cupid_pair,
    choose_wild_child_idol,
)


class GameSpecialRolesTests(unittest.TestCase):
    def test_choose_cupid_pair_accepts_valid_pair_and_repairs_invalid_one(self):
        self.assertEqual(choose_cupid_pair([1, 2, 3], [1, 3]), [1, 3])

        random.seed(5)
        repaired = choose_cupid_pair([1, 2, 3], [1, 1])
        self.assertEqual(len(repaired), 2)
        self.assertNotEqual(repaired[0], repaired[1])
        self.assertTrue(all(seat in [1, 2, 3] for seat in repaired))

    def test_choose_wild_child_idol_accepts_valid_target_and_repairs_invalid_one(self):
        self.assertEqual(choose_wild_child_idol([2, 3, 4], 3), 3)

        random.seed(6)
        repaired = choose_wild_child_idol([2, 3, 4], 9)
        self.assertIn(repaired, {2, 3, 4})

    def test_apply_helpers_write_player_relationships(self):
        players = {
            1: Player(seat=1, role=Role.CUPID, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
            3: Player(seat=3, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
            4: Player(seat=4, role=Role.WILD_CHILD, camp=Camp.GOOD, is_human=False),
        }

        self.assertTrue(apply_cupid_pair(players, [2, 3]))
        self.assertEqual(players[2].lover, 3)
        self.assertEqual(players[3].lover, 2)

        self.assertTrue(apply_wild_child_idol(players[4], 2))
        self.assertEqual(players[4].idol, 2)
