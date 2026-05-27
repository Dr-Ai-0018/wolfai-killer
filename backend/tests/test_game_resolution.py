import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_catalog import Camp, Role
from game_engine import Player
from game_resolution import (
    determine_winner,
    find_lover_chain_target,
    resolve_immediate_elimination_rule,
    should_disable_powers_for_elder,
    awaken_wild_children,
)


class GameResolutionTests(unittest.TestCase):
    def test_determine_winner_handles_angel_lovers_and_camp_results(self):
        players = {
            1: Player(seat=1, role=Role.VILLAGER, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
        }
        players[1].lover = 2
        players[2].lover = 1
        self.assertEqual(determine_winner(players, angel_victory_seat=3), "天使阵营")
        self.assertEqual(determine_winner(players, angel_victory_seat=None), "情侣阵营")

        players[1].lover = None
        players[2].lover = None
        self.assertEqual(determine_winner(players, angel_victory_seat=None), "狼人阵营")
        players[2].alive = False
        self.assertEqual(determine_winner(players, angel_victory_seat=None), "好人阵营")

    def test_resolve_immediate_elimination_rule_covers_special_roles(self):
        angel = Player(seat=1, role=Role.ANGEL, camp=Camp.GOOD, is_human=True)
        self.assertEqual(resolve_immediate_elimination_rule(angel, "vote", day_count=1).kind, "angel_victory")
        self.assertFalse(angel.alive)
        self.assertFalse(angel.angel_active)

        elder = Player(seat=2, role=Role.ELDER, camp=Camp.GOOD, is_human=True)
        self.assertEqual(resolve_immediate_elimination_rule(elder, "wolf_kill", day_count=2).kind, "elder_survive")
        self.assertEqual(elder.elder_lives, 1)

        blessed = Player(seat=3, role=Role.BLESSED, camp=Camp.GOOD, is_human=True)
        self.assertEqual(resolve_immediate_elimination_rule(blessed, "wolf_kill", day_count=2).kind, "blessed_survive")
        self.assertTrue(blessed.blessing_used)

        cursed = Player(seat=4, role=Role.CURSED, camp=Camp.GOOD, is_human=True)
        self.assertEqual(resolve_immediate_elimination_rule(cursed, "wolf_kill", day_count=2).kind, "cursed_turn")
        self.assertEqual(cursed.camp, Camp.WOLF)
        self.assertTrue(cursed.cursed_turned)

        idiot = Player(seat=5, role=Role.IDIOT, camp=Camp.GOOD, is_human=True)
        self.assertEqual(resolve_immediate_elimination_rule(idiot, "vote", day_count=2).kind, "idiot_reveal")
        self.assertTrue(idiot.idiot_revealed)
        self.assertFalse(idiot.can_vote)

    def test_find_lover_chain_target_and_awaken_wild_children(self):
        players = {
            1: Player(seat=1, role=Role.VILLAGER, camp=Camp.GOOD, is_human=True, lover=2),
            2: Player(seat=2, role=Role.WOLF, camp=Camp.WOLF, is_human=False, lover=1),
            3: Player(seat=3, role=Role.WILD_CHILD, camp=Camp.GOOD, is_human=False, idol=1),
        }

        self.assertEqual(find_lover_chain_target(players, 1), 2)
        awakened = awaken_wild_children(players, 1)

        self.assertEqual(awakened, [3])
        self.assertEqual(players[3].camp, Camp.WOLF)
        self.assertTrue(players[3].wild_child_awakened)
        self.assertTrue(should_disable_powers_for_elder("vote"))
        self.assertFalse(should_disable_powers_for_elder("lover_suicide"))
