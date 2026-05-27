import asyncio
import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_engine import Camp, GameEngine, GamePhase, PERSONALITIES, Player, Role


APP_PATH = ROOT / "app.py"
SPEC = importlib.util.spec_from_file_location("wolf_backend_app_file", APP_PATH)
APPFILE = importlib.util.module_from_spec(SPEC)
sys.modules["wolf_backend_app_file"] = APPFILE
assert SPEC.loader is not None
SPEC.loader.exec_module(APPFILE)


def load_config():
    APPFILE.game_manager.load_config()
    return APPFILE.game_manager.config


def make_engine(game_id: str) -> GameEngine:
    engine = GameEngine(game_id, load_config(), god_mode_password="gm-test")
    engine.total_players = 0

    async def dummy_broadcast(event, data, to_seat=None):
        return None

    engine.set_broadcast(dummy_broadcast)
    return engine


class ExtensionRoleTests(unittest.IsolatedAsyncioTestCase):
    async def test_mason_private_view_contains_other_masons_only(self):
        engine = make_engine("test-mason-private-view")
        engine.players = {
            1: Player(seat=1, role=Role.MASON, camp=Camp.GOOD, is_human=True, mason_peers=[2]),
            2: Player(seat=2, role=Role.MASON, camp=Camp.GOOD, is_human=False, mason_peers=[1]),
            3: Player(seat=3, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
        }

        seat_1_view = engine.players[1].to_private_dict()
        seat_2_view = engine.players[2].to_private_dict()
        seat_3_view = engine.players[3].to_private_dict()

        self.assertEqual(seat_1_view["mason_peers"], [2])
        self.assertEqual(seat_2_view["mason_peers"], [1])
        self.assertNotIn("mason_peers", seat_3_view)

    async def test_super_saint_vote_elimination_reflects_last_voter(self):
        engine = make_engine("test-super-saint")
        engine.players = {
            1: Player(seat=1, role=Role.SUPER_SAINT, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
            3: Player(seat=3, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
            4: Player(seat=4, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
        }
        engine.phase = GamePhase.VOTE

        eliminated_chain = await engine.eliminate_player(1, "vote", allow_hunter=False, context={"last_voter": 4})

        self.assertEqual(eliminated_chain, [1, 4])
        self.assertFalse(engine.players[1].alive)
        self.assertFalse(engine.players[4].alive)
        self.assertTrue(any(log["type"] == "super_saint" for log in engine.logs))

    async def test_idiot_vote_reveal_keeps_player_alive_and_logs_vote_result(self):
        engine = make_engine("test-idiot")
        engine.players = {
            1: Player(seat=1, role=Role.IDIOT, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
            3: Player(seat=3, role=Role.SEER, camp=Camp.GOOD, is_human=False),
        }
        engine.phase = GamePhase.VOTE

        eliminated_chain = await engine.eliminate_player(1, "vote")
        if eliminated_chain:
            engine.add_log(
                "eliminate",
                "1号被投票出局（2票）",
                meta={"eliminated": 1, "votes": 2, "vote_counts": {1: 2}, "chain": eliminated_chain},
            )
        else:
            engine.add_log(
                "vote_result",
                "1号获得最多票（2票），但未实际出局。",
                meta={"seat": 1, "votes": 2, "vote_counts": {1: 2}, "eliminated": False},
            )

        self.assertEqual(eliminated_chain, [])
        self.assertTrue(engine.players[1].alive)
        self.assertTrue(engine.players[1].idiot_revealed)
        self.assertFalse(engine.players[1].can_vote)
        self.assertTrue(any(log["type"] == "vote_result" for log in engine.logs))
        self.assertFalse(any(log["type"] == "eliminate" for log in engine.logs))

    async def test_wild_child_awakens_after_idol_death(self):
        engine = make_engine("test-wild-child")
        engine.players = {
            1: Player(seat=1, role=Role.WILD_CHILD, camp=Camp.GOOD, is_human=True, idol=2),
            2: Player(seat=2, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
            3: Player(seat=3, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
        }

        eliminated = await engine.eliminate_player(2, "vote", allow_hunter=False)

        self.assertEqual(eliminated, [2])
        self.assertEqual(engine.players[1].camp, Camp.WOLF)
        self.assertTrue(engine.players[1].wild_child_awakened)
        self.assertTrue(any(log["type"] == "wild_child_awaken" for log in engine.logs))

    async def test_idiot_loses_vote_rights_on_later_vote_round(self):
        engine = make_engine("test-idiot-followup-vote")
        engine.players = {
            1: Player(seat=1, role=Role.IDIOT, camp=Camp.GOOD, is_human=True),
            2: Player(
                seat=2,
                role=Role.VILLAGER,
                camp=Camp.GOOD,
                is_human=False,
                model_name="gpt-5.4-mini",
                personality=PERSONALITIES[0],
            ),
            3: Player(
                seat=3,
                role=Role.WOLF,
                camp=Camp.WOLF,
                is_human=False,
                model_name="gpt-5.4",
                personality=PERSONALITIES[1],
            ),
        }

        await engine.eliminate_player(1, "vote")
        self.assertFalse(engine.players[1].can_vote)
        engine.total_players = len(engine.players)
        engine.players[1].alive = False
        engine.day_count = 2
        await engine.run_vote()

        later_vote_logs = [
            log
            for log in engine.logs
            if log["type"] == "vote" and log.get("meta", {}).get("voter") == 1
        ]
        self.assertFalse(later_vote_logs)

    async def test_wild_child_full_log_chain_includes_private_conversion_notice(self):
        engine = make_engine("test-wild-child-log-chain")
        engine.players = {
            1: Player(seat=1, role=Role.WILD_CHILD, camp=Camp.GOOD, is_human=True, idol=2),
            2: Player(seat=2, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
            3: Player(seat=3, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
        }

        await engine.eliminate_player(2, "wolf_kill", allow_hunter=False)

        private_awaken = [log for log in engine.logs if log["type"] == "wild_child_awaken"]
        private_summary = [
            log for log in engine.logs
            if log["type"] == "system" and not log.get("is_public", True) and "秘密转化为狼人" in log["content"]
        ]

        self.assertTrue(private_awaken)
        self.assertTrue(private_summary)
        self.assertEqual(engine.players[1].camp, Camp.WOLF)

    async def test_cursed_turns_to_wolf_instead_of_dying_on_first_wolf_kill(self):
        engine = make_engine("test-cursed-turns")
        engine.players = {
            1: Player(seat=1, role=Role.CURSED, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
            3: Player(seat=3, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
        }

        eliminated = await engine.eliminate_player(1, "wolf_kill", allow_hunter=False)

        self.assertEqual(eliminated, [])
        self.assertTrue(engine.players[1].alive)
        self.assertEqual(engine.players[1].camp, Camp.WOLF)
        self.assertTrue(engine.players[1].cursed_turned)
        self.assertTrue(any("秘密转入狼人阵营" in log["content"] for log in engine.logs))

    async def test_blessed_survives_first_wolf_kill_then_dies_on_second(self):
        engine = make_engine("test-blessed-survival")
        engine.players = {
            1: Player(seat=1, role=Role.BLESSED, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
            3: Player(seat=3, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
        }

        first = await engine.eliminate_player(1, "wolf_kill", allow_hunter=False)
        second = await engine.eliminate_player(1, "wolf_kill", allow_hunter=False)

        self.assertEqual(first, [])
        self.assertTrue(engine.players[1].blessing_used)
        self.assertEqual(second, [1])
        self.assertFalse(engine.players[1].alive)

    async def test_elder_survives_first_wolf_kill_then_dies_on_second(self):
        engine = make_engine("test-elder-survival")
        engine.players = {
            1: Player(seat=1, role=Role.ELDER, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
            3: Player(seat=3, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
        }

        first = await engine.eliminate_player(1, "wolf_kill", allow_hunter=False)

        self.assertEqual(first, [])
        self.assertEqual(engine.players[1].elder_lives, 1)
        self.assertTrue(engine.players[1].alive)

        second = await engine.eliminate_player(1, "wolf_kill", allow_hunter=False)

        self.assertEqual(second, [1])
        self.assertFalse(engine.players[1].alive)
        self.assertFalse(engine.powers_disabled)
        self.assertTrue(any("长老承受了第一次狼人袭击" in log["content"] for log in engine.logs))

    async def test_elder_vote_death_disables_good_powers(self):
        engine = make_engine("test-elder-vote-death")
        engine.players = {
            1: Player(seat=1, role=Role.ELDER, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.SEER, camp=Camp.GOOD, is_human=False),
            3: Player(seat=3, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
        }
        engine.phase = GamePhase.VOTE

        eliminated = await engine.eliminate_player(1, "vote", allow_hunter=False)

        self.assertEqual(eliminated, [1])
        self.assertTrue(engine.powers_disabled)
        self.assertTrue(any("长老以非狼人袭击的方式死亡" in log["content"] for log in engine.logs))

    async def test_cupid_pair_causes_lover_suicide_chain(self):
        engine = make_engine("test-cupid-lover-chain")
        engine.players = {
            1: Player(seat=1, role=Role.CUPID, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False, lover=3),
            3: Player(seat=3, role=Role.WOLF, camp=Camp.WOLF, is_human=False, lover=2),
        }

        eliminated = await engine.eliminate_player(2, "vote", allow_hunter=False)

        self.assertEqual(eliminated, [2, 3])
        self.assertFalse(engine.players[2].alive)
        self.assertFalse(engine.players[3].alive)
        self.assertTrue(any("情侣殉情" in log["content"] for log in engine.logs))

    async def test_fox_private_view_contains_checks_and_power_state(self):
        fox = Player(seat=1, role=Role.FOX, camp=Camp.GOOD, is_human=True, fox_checks={3: "有狼人"}, fox_power_active=False)
        private_view = fox.to_private_dict()

        self.assertEqual(private_view["fox_checks"], {3: "有狼人"})
        self.assertFalse(private_view["fox_power_active"])

    async def test_fox_neighbor_triplet_wraps_correctly(self):
        engine = make_engine("test-fox-neighbors")
        engine.players = {
            1: Player(seat=1, role=Role.FOX, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
            3: Player(seat=3, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
            4: Player(seat=4, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
        }

        self.assertEqual(engine.get_neighbor_triplet(1), [4, 1, 2])
        self.assertEqual(engine.get_neighbor_triplet(3), [2, 3, 4])

    async def test_fox_loses_power_after_clean_sniff(self):
        engine = make_engine("test-fox-clean-sniff")
        engine.players = {
            1: Player(seat=1, role=Role.FOX, camp=Camp.GOOD, is_human=False),
            2: Player(seat=2, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
            3: Player(seat=3, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
            4: Player(seat=4, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
            5: Player(seat=5, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
        }

        original_choice = __import__("random").choice
        __import__("random").choice = lambda options: 2
        try:
            await engine.fox_action_with_phantom()
        finally:
            __import__("random").choice = original_choice

        self.assertEqual(engine.players[1].fox_checks[2], "没有狼人")
        self.assertFalse(engine.players[1].fox_power_active)
        self.assertTrue(any("失去了后续嗅探能力" in log["content"] for log in engine.logs))

    async def test_angel_wins_if_voted_out_on_first_day(self):
        engine = make_engine("test-angel-vote-win")
        engine.players = {
            1: Player(seat=1, role=Role.ANGEL, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
            3: Player(seat=3, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
        }
        engine.day_count = 1
        engine.phase = GamePhase.VOTE

        eliminated = await engine.eliminate_player(1, "vote", allow_hunter=False)

        self.assertEqual(eliminated, [1])
        self.assertEqual(engine.check_winner(), "天使阵营")
        self.assertTrue(any(log["type"] == "angel_victory" for log in engine.logs))

    async def test_angel_wins_if_killed_by_wolves_on_first_night(self):
        engine = make_engine("test-angel-wolf-win")
        engine.players = {
            1: Player(seat=1, role=Role.ANGEL, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
            3: Player(seat=3, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
        }
        engine.day_count = 0

        eliminated = await engine.eliminate_player(1, "wolf_kill", allow_hunter=False)

        self.assertEqual(eliminated, [1])
        self.assertEqual(engine.check_winner(), "天使阵营")
        self.assertTrue(any(log["type"] == "angel_victory" for log in engine.logs))

    async def test_scapegoat_replaces_tie_and_restricts_next_vote(self):
        engine = make_engine("test-scapegoat-tie")
        engine.players = {
            1: Player(seat=1, role=Role.SCAPEGOAT, camp=Camp.GOOD, is_human=True),
            2: Player(seat=2, role=Role.WOLF, camp=Camp.WOLF, is_human=False),
            3: Player(seat=3, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
            4: Player(seat=4, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
            5: Player(seat=5, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False),
        }

        async def fake_wait_for_human(seat, action_type, options, timeout=120):
            if action_type == "scapegoat":
                return {"allowed_voters": [2, 3]}
            if action_type == "vote":
                return {"target": 4}
            return None

        engine.wait_for_human = fake_wait_for_human  # type: ignore[method-assign]

        async def fake_ai_vote(player, valid_targets, votes):
            if player.seat == 2:
                return 3
            if player.seat == 4:
                return 3
            return 2

        engine.generate_ai_vote = fake_ai_vote  # type: ignore[method-assign]
        engine.total_players = len(engine.players)

        await engine.run_vote()

        self.assertFalse(engine.players[1].alive)
        self.assertEqual(engine.restricted_voters_next_day, {2, 3})
        self.assertEqual(engine.players[1].scapegoat_allow_voters, [2, 3])
        self.assertTrue(any("替罪羊替死出局" in log["content"] for log in engine.logs))
        self.assertTrue(any(log["type"] == "scapegoat_choice" for log in engine.logs))


if __name__ == "__main__":
    unittest.main()
