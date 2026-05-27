import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_vote import (
    apply_vote_rights,
    build_cast_vote_log,
    build_human_vote_options,
    build_skipped_vote_log,
    build_scapegoat_tie_log,
    build_valid_vote_targets,
    build_vote_eliminate_log,
    build_vote_result_log,
    build_vote_tie_log,
    count_votes,
    record_vote_choice,
    resolve_vote_round,
)


class DummyPlayer:
    def __init__(self):
        self.can_vote = True


class GameVoteTests(unittest.TestCase):
    def test_apply_vote_rights_allows_everyone_without_restriction(self):
        players = {1: DummyPlayer(), 2: DummyPlayer(), 3: DummyPlayer()}

        active = apply_vote_rights(players, [1, 2, 3], None)

        self.assertEqual(active, set())
        self.assertTrue(players[1].can_vote)
        self.assertTrue(players[2].can_vote)
        self.assertTrue(players[3].can_vote)

    def test_apply_vote_rights_limits_to_allowed_subset(self):
        players = {1: DummyPlayer(), 2: DummyPlayer(), 3: DummyPlayer()}

        active = apply_vote_rights(players, [1, 2, 3], {2, 3})

        self.assertEqual(active, {2, 3})
        self.assertFalse(players[1].can_vote)
        self.assertTrue(players[2].can_vote)
        self.assertTrue(players[3].can_vote)

    def test_count_and_resolve_votes_for_single_elimination(self):
        votes = {1: 3, 2: 3, 3: 2}

        counts = count_votes(votes)
        resolution = resolve_vote_round(votes)

        self.assertEqual(counts, {3: 2, 2: 1})
        assert resolution is not None
        self.assertFalse(resolution.is_tie)
        self.assertEqual(resolution.eliminated_seat, 3)
        self.assertEqual(resolution.max_votes, 2)
        self.assertEqual(resolution.top_targets, [3])

    def test_build_valid_vote_targets_excludes_self(self):
        self.assertEqual(build_valid_vote_targets([1, 2, 3, 4], 3), [1, 2, 4])

    def test_build_human_vote_options_copies_current_votes(self):
        votes = {1: 3}

        options = build_human_vote_options([2, 3], votes)
        votes[2] = 1

        self.assertEqual(options, {"candidates": [2, 3], "current_votes": {1: 3}, "message": "请投票"})

    def test_record_vote_choice_updates_votes_and_last_voter(self):
        votes = {1: 3}
        last_voter_by_target = {3: 1}

        record_vote_choice(votes, last_voter_by_target, 2, 3)

        self.assertEqual(votes, {1: 3, 2: 3})
        self.assertEqual(last_voter_by_target, {3: 2})

    def test_resolve_vote_round_returns_none_without_votes(self):
        self.assertIsNone(resolve_vote_round({}))

    def test_resolve_vote_round_detects_tie(self):
        resolution = resolve_vote_round({1: 2, 2: 3, 3: 2, 4: 3})

        assert resolution is not None
        self.assertTrue(resolution.is_tie)
        self.assertIsNone(resolution.eliminated_seat)
        self.assertEqual(resolution.max_votes, 2)
        self.assertEqual(resolution.top_targets, [2, 3])

    def test_build_vote_logs(self):
        resolution = resolve_vote_round({1: 3, 2: 3, 3: 2})
        assert resolution is not None

        eliminate_payload = build_vote_eliminate_log(resolution, [3, 4])
        result_payload = build_vote_result_log(resolution)
        cast_payload = build_cast_vote_log(2, 3)
        skipped_payload = build_skipped_vote_log(1)

        self.assertEqual(eliminate_payload["type"], "eliminate")
        self.assertEqual(eliminate_payload["meta"]["chain"], [3, 4])
        self.assertEqual(result_payload["type"], "vote_result")
        self.assertFalse(result_payload["meta"]["eliminated"])
        self.assertEqual(cast_payload["meta"], {"voter": 2, "target": 3})
        self.assertEqual(skipped_payload["meta"], {"voter": 1, "skipped": True})

    def test_build_tie_logs(self):
        resolution = resolve_vote_round({1: 2, 2: 3, 3: 2, 4: 3})
        assert resolution is not None

        scapegoat_payload = build_scapegoat_tie_log(resolution, 1, [1])
        tie_payload = build_vote_tie_log(resolution)

        self.assertEqual(scapegoat_payload["type"], "eliminate")
        self.assertEqual(scapegoat_payload["meta"]["tie_targets"], [2, 3])
        self.assertEqual(tie_payload["type"], "vote")
        self.assertEqual(tie_payload["meta"]["vote_counts"], {2: 2, 3: 2})


if __name__ == "__main__":
    unittest.main()
