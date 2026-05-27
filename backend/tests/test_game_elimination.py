import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_catalog import Camp, Role
from game_elimination import (
    apply_primary_elimination,
    resolve_hunter_chain,
    resolve_immediate_elimination,
    resolve_post_elimination_effects,
    resolve_super_saint_revenge,
)
from game_engine import Player


class EliminationEngineStub:
    def __init__(self):
        self.players = {}
        self.day_count = 0
        self.logs = []
        self.angel_victory_seat = None
        self.powers_disabled = False
        self.emitted = []
        self.hunter_calls = []
        self.awakened = {}
        self.eliminate_calls = []

    def add_log(self, log_type, content, seat=None, is_public=True, meta=None):
        self.logs.append(
            {
                "type": log_type,
                "content": content,
                "seat": seat,
                "is_public": is_public,
                "meta": meta or {},
            }
        )

    async def emit(self, event, data, to_seat=None):
        self.emitted.append({"event": event, "data": data, "to_seat": to_seat})

    def should_disable_powers_for_elder(self, cause):
        return cause == "vote"

    def disable_good_powers(self):
        self.powers_disabled = True

    async def awaken_wild_children_for_idol(self, dead_seat):
        return list(self.awakened.get(dead_seat, []))

    async def eliminate_player(self, seat, cause, allow_hunter=True, context=None):
        self.eliminate_calls.append(
            {"seat": seat, "cause": cause, "allow_hunter": allow_hunter, "context": context or {}}
        )
        self.players[seat].alive = False
        return [seat]

    async def hunter_action(self, seat):
        self.hunter_calls.append(seat)


class GameEliminationTests(unittest.IsolatedAsyncioTestCase):
    async def test_resolve_immediate_elimination_handles_cursed_turn_and_emits_private_notice(self):
        engine = EliminationEngineStub()
        engine.day_count = 2
        engine.players = {
            1: Player(seat=1, role=Role.CURSED, camp=Camp.GOOD, is_human=True),
        }

        result = await resolve_immediate_elimination(engine, 1, "wolf_kill")

        self.assertEqual(result, [])
        self.assertEqual(engine.players[1].camp, Camp.WOLF)
        self.assertEqual(engine.emitted[0]["event"], "cursed_turned")
        self.assertFalse(engine.logs[0]["is_public"])

    def test_apply_primary_elimination_handles_lover_chain_and_elder_power_disable(self):
        engine = EliminationEngineStub()
        engine.players = {
            1: Player(seat=1, role=Role.ELDER, camp=Camp.GOOD, is_human=True, lover=2),
            2: Player(seat=2, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False, lover=1),
        }

        eliminated = apply_primary_elimination(engine, 1, "vote")

        self.assertEqual(eliminated, [1, 2])
        self.assertFalse(engine.players[1].alive)
        self.assertFalse(engine.players[2].alive)
        self.assertTrue(engine.powers_disabled)
        self.assertTrue(any("情侣殉情" in log["content"] for log in engine.logs))

    async def test_resolve_post_elimination_effects_aggregates_awakened_children(self):
        engine = EliminationEngineStub()
        engine.awakened = {2: [5], 3: [6]}

        await resolve_post_elimination_effects(engine, [2, 3])

        self.assertTrue(any(log["type"] == "system" and not log["is_public"] for log in engine.logs))
        self.assertEqual(engine.logs[0]["meta"]["awakened"], [5, 6])

    async def test_resolve_super_saint_revenge_eliminates_last_voter(self):
        engine = EliminationEngineStub()
        saint = Player(seat=1, role=Role.SUPER_SAINT, camp=Camp.GOOD, is_human=True)
        voter = Player(seat=4, role=Role.WOLF, camp=Camp.WOLF, is_human=False)
        engine.players = {1: saint, 4: voter}

        eliminated = [1]
        await resolve_super_saint_revenge(
            engine,
            saint,
            1,
            "vote",
            True,
            {"last_voter": 4},
            eliminated,
        )

        self.assertEqual(eliminated, [1, 4])
        self.assertEqual(engine.eliminate_calls[0]["context"], {"triggered_by": 1})
        self.assertTrue(any(log["type"] == "super_saint" for log in engine.logs))

    async def test_resolve_hunter_chain_skips_when_disabled_or_disallowed(self):
        engine = EliminationEngineStub()
        engine.players = {
            2: Player(seat=2, role=Role.HUNTER, camp=Camp.GOOD, is_human=True),
            3: Player(seat=3, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
        }

        await resolve_hunter_chain(engine, [2, 3], allow_hunter=False)
        self.assertEqual(engine.hunter_calls, [])

        await resolve_hunter_chain(engine, [2, 3], allow_hunter=True)
        self.assertEqual(engine.hunter_calls, [2])

        engine.powers_disabled = True
        await resolve_hunter_chain(engine, [2], allow_hunter=True)
        self.assertEqual(engine.hunter_calls, [2])


if __name__ == "__main__":
    unittest.main()
