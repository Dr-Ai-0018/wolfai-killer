import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_catalog import Camp, Role
from game_engine import Player
from game_vote_flow import collect_vote_round, resolve_vote_outcome


class VoteFlowEngineStub:
    def __init__(self):
        self.players = {}
        self.logs = []
        self.restricted_voters_next_day = None
        self.human_votes = {}
        self.ai_votes = {}
        self.eliminate_calls = []
        self.scapegoat_choices = []
        self.state_emits = 0

    def get_alive_seats(self):
        return [seat for seat, player in self.players.items() if player.alive]

    def add_log(self, log_type, content, seat=None, meta=None):
        self.logs.append({"type": log_type, "content": content, "seat": seat, "meta": meta or {}})

    async def emit_state(self):
        self.state_emits += 1

    async def wait_for_human(self, seat, action_type, options):
        return {"target": self.human_votes.get(seat)}

    async def generate_ai_vote(self, player, valid_targets, votes):
        return self.ai_votes.get(player.seat)

    async def eliminate_player(self, seat, cause, allow_hunter=True, context=None):
        self.eliminate_calls.append(
            {"seat": seat, "cause": cause, "allow_hunter": allow_hunter, "context": context or {}}
        )
        self.players[seat].alive = False
        return [seat]

    def get_player_by_role(self, role):
        for player in self.players.values():
            if player.role == role and player.alive:
                return player
        return None

    async def scapegoat_choose_voters(self, scapegoat_seat):
        self.scapegoat_choices.append(scapegoat_seat)
        self.restricted_voters_next_day = {2, 3}
        self.players[scapegoat_seat].scapegoat_allow_voters = [2, 3]
        self.add_log(
            "scapegoat_choice",
            "1号替罪羊指定下一天仅有2号、3号保有投票权。",
            seat=scapegoat_seat,
            meta={"seat": scapegoat_seat, "allowed_voters": [2, 3]},
        )
        return [2, 3]


class GameVoteFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_collect_vote_round_respects_restricted_voters_and_logs_skips(self):
        engine = VoteFlowEngineStub()
        engine.players = {
            1: Player(seat=1, role=Role.VILLAGER, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
            3: Player(seat=3, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
        }
        engine.restricted_voters_next_day = {2, 3}
        engine.ai_votes = {2: 3, 3: 2}
        engine.human_votes = {1: 2}

        votes, last_voter_by_target = await collect_vote_round(engine)

        self.assertIsNone(engine.restricted_voters_next_day)
        self.assertEqual(votes, {2: 3, 3: 2})
        self.assertEqual(last_voter_by_target, {3: 2, 2: 3})
        self.assertFalse(engine.players[1].can_vote)
        self.assertTrue(any(log["meta"].get("skipped") for log in engine.logs))

    async def test_resolve_vote_outcome_eliminates_top_target_with_last_voter_context(self):
        engine = VoteFlowEngineStub()
        engine.players = {
            1: Player(seat=1, role=Role.VILLAGER, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
            3: Player(seat=3, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
        }

        await resolve_vote_outcome(engine, {1: 2, 3: 2}, {2: 3})

        self.assertEqual(engine.eliminate_calls[0]["seat"], 2)
        self.assertEqual(engine.eliminate_calls[0]["context"], {"last_voter": 3})
        self.assertTrue(any(log["type"] == "eliminate" for log in engine.logs))

    async def test_resolve_vote_outcome_uses_scapegoat_on_tie(self):
        engine = VoteFlowEngineStub()
        engine.players = {
            1: Player(seat=1, role=Role.SCAPEGOAT, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
            3: Player(seat=3, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
            4: Player(seat=4, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
        }

        await resolve_vote_outcome(engine, {2: 3, 3: 2, 4: 3, 1: 2}, {2: 4, 3: 1})

        self.assertEqual(engine.eliminate_calls[0]["seat"], 1)
        self.assertEqual(engine.eliminate_calls[0]["cause"], "scapegoat")
        self.assertEqual(engine.eliminate_calls[0]["context"], {"tie_targets": [3, 2]})
        self.assertEqual(engine.scapegoat_choices, [1])
        self.assertTrue(any(log["type"] == "scapegoat_choice" for log in engine.logs))
        self.assertTrue(any("替罪羊替死出局" in log["content"] for log in engine.logs))


if __name__ == "__main__":
    unittest.main()
