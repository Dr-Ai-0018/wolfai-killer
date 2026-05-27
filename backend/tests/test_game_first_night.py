import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_catalog import Camp, Role
from game_engine import Player
from game_first_night import run_cupid_action, run_wild_child_action


class FirstNightEngineStub:
    def __init__(self):
        self.players = {}
        self.night_count = 1
        self.cupid_paired = False
        self.logs = []
        self.emits = []
        self.phantom_actions = []
        self.responses = {}

    def get_player_by_role_any(self, role):
        for player in self.players.values():
            if player.role == role:
                return player
        return None

    def get_alive_seats(self):
        return [seat for seat, player in self.players.items() if player.alive]

    async def wait_for_human(self, seat, action_type, options):
        return self.responses.get((seat, action_type))

    def add_log(self, log_type, content, seat=None, is_public=True, meta=None):
        self.logs.append(
            {"type": log_type, "content": content, "seat": seat, "is_public": is_public, "meta": meta or {}}
        )

    async def emit(self, event, data, to_seat=None):
        self.emits.append({"event": event, "data": data, "to_seat": to_seat})

    def add_phantom_action(self, role, seat, action_type, target, decision, night):
        self.phantom_actions.append(
            {
                "role": role,
                "seat": seat,
                "action_type": action_type,
                "target": target,
                "decision": decision,
                "night": night,
            }
        )


class GameFirstNightTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_cupid_action_pairs_requested_players_and_emits_lover_info(self):
        engine = FirstNightEngineStub()
        engine.players = {
            1: Player(seat=1, role=Role.CUPID, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
            3: Player(seat=3, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
        }
        engine.responses[(1, "cupid")] = {"pair": [2, 3]}

        await run_cupid_action(engine)

        self.assertTrue(engine.cupid_paired)
        self.assertEqual(engine.players[2].lover, 3)
        self.assertEqual(engine.players[3].lover, 2)
        self.assertTrue(any(log["type"] == "cupid_action" for log in engine.logs))
        self.assertEqual([emit["event"] for emit in engine.emits], ["lover_info", "lover_info"])

    async def test_run_cupid_action_records_dead_ai_phantom_decision(self):
        engine = FirstNightEngineStub()
        engine.players = {
            1: Player(seat=1, role=Role.CUPID, camp=Camp.GOOD, is_human=False, alive=False),
            2: Player(seat=2, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
            3: Player(seat=3, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
        }

        await run_cupid_action(engine)

        self.assertFalse(engine.cupid_paired)
        self.assertEqual(len(engine.phantom_actions), 1)
        self.assertEqual(engine.phantom_actions[0]["role"], "丘比特")

    async def test_run_wild_child_action_sets_idol_and_emits_private_info(self):
        engine = FirstNightEngineStub()
        engine.players = {
            4: Player(seat=4, role=Role.WILD_CHILD, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
            3: Player(seat=3, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
        }
        engine.responses[(4, "wild_child")] = {"target": 2}

        await run_wild_child_action(engine)

        self.assertEqual(engine.players[4].idol, 2)
        self.assertTrue(any(log["type"] == "wild_child_action" for log in engine.logs))
        self.assertEqual(engine.emits[0], {"event": "wild_child_info", "data": {"idol": 2}, "to_seat": 4})

    async def test_run_wild_child_action_skips_when_idol_already_set(self):
        engine = FirstNightEngineStub()
        engine.players = {
            4: Player(seat=4, role=Role.WILD_CHILD, camp=Camp.GOOD, is_human=True, idol=2),
            2: Player(seat=2, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
        }

        await run_wild_child_action(engine)

        self.assertEqual(engine.logs, [])
        self.assertEqual(engine.emits, [])


if __name__ == "__main__":
    unittest.main()
