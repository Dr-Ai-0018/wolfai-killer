import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import game_day_ai
from game_catalog import Camp, Role
from game_engine import Player
from game_day_ai import (
    build_day_speech_user_prompt,
    build_day_vote_scores,
    build_day_vote_user_prompt,
    build_llm_messages,
    choose_speech_fallback,
    choose_vote_fallback,
    parse_ai_vote_response,
)


class GameDayAiTests(unittest.TestCase):
    def test_build_day_speech_user_prompt_includes_context_and_extra_info(self):
        prompt = build_day_speech_user_prompt(3, "局面摘要", "隐藏信息")

        self.assertIn("3 号玩家", prompt)
        self.assertIn("局面摘要", prompt)
        self.assertIn("隐藏信息", prompt)

    def test_build_day_vote_user_prompt_includes_context(self):
        prompt = build_day_vote_user_prompt(2, "当前投票上下文")

        self.assertIn("2 号玩家", prompt)
        self.assertIn("当前投票上下文", prompt)
        self.assertIn('{"target": 座位号整数}', prompt)

    def test_build_llm_messages_returns_system_and_user_messages(self):
        messages = build_llm_messages("sys", "user")

        self.assertEqual(messages, [{"role": "system", "content": "sys"}, {"role": "user", "content": "user"}])

    def test_parse_ai_vote_response_returns_first_valid_candidate(self):
        self.assertEqual(parse_ai_vote_response('{"target": 5, "note": "先出3"}', [3, 4]), 3)

    def test_parse_ai_vote_response_returns_none_when_no_candidate_matches(self):
        self.assertIsNone(parse_ai_vote_response('{"target": 7}', [1, 2, 3]))
        self.assertIsNone(parse_ai_vote_response(None, [1, 2, 3]))

    def test_choose_speech_fallback_handles_no_targets(self):
        self.assertIn("信息不多", choose_speech_fallback(4, []))

    def test_choose_speech_fallback_uses_first_alive_candidate(self):
        speech = choose_speech_fallback(1, [3, 5])

        self.assertIn("3号", speech)
        self.assertIn("压力位", speech)

    def test_choose_vote_fallback_prefers_top_score_above_threshold(self):
        original_choice = game_day_ai.random.choice
        game_day_ai.random.choice = lambda options: options[-1]
        try:
            target = choose_vote_fallback([2, 3, 4], {2: 1, 3: 1, 4: -3})
        finally:
            game_day_ai.random.choice = original_choice

        self.assertEqual(target, 3)

    def test_choose_vote_fallback_falls_back_to_candidate_list(self):
        original_choice = game_day_ai.random.choice
        game_day_ai.random.choice = lambda options: options[0]
        try:
            target = choose_vote_fallback([2, 3], {2: -60, 3: -70})
        finally:
            game_day_ai.random.choice = original_choice

        self.assertEqual(target, 2)

    def test_build_day_vote_scores_protects_single_claimed_power_role_for_good_camp(self):
        player = Player(seat=1, role=Role.VILLAGER, camp=Camp.GOOD, is_human=False)
        logs = [
            {
                "type": "speech",
                "seat": 2,
                "content": "我是2号，身份是预言家。今天先听发言，先不出2号。",
                "is_public": True,
                "day": 1,
                "meta": {"claimed_role": "预言家"},
            }
        ]

        scores = build_day_vote_scores(
            player=player,
            candidates=[2, 3],
            current_votes={},
            claims={"预言家": [2]},
            logs=logs,
            day_count=1,
            total_players=6,
            get_neighbor_triplet=lambda seat: [seat - 1, seat, seat + 1],
            alive_wolf_seats=[],
        )

        self.assertLess(scores[2], scores[3])

    def test_build_day_vote_scores_seer_check_overrides_to_wolf_target(self):
        player = Player(
            seat=1,
            role=Role.SEER,
            camp=Camp.GOOD,
            is_human=False,
            seer_results={3: "狼人", 4: "好人"},
        )

        scores = build_day_vote_scores(
            player=player,
            candidates=[2, 3, 4],
            current_votes={},
            claims={},
            logs=[],
            day_count=2,
            total_players=6,
            get_neighbor_triplet=lambda seat: [seat - 1, seat, seat + 1],
            alive_wolf_seats=[],
        )

        self.assertGreater(scores[3], scores[2])
        self.assertLess(scores[4], scores[2])

    def test_build_day_vote_scores_wolf_avoids_alive_teammates(self):
        player = Player(seat=1, role=Role.WOLF, camp=Camp.WOLF, is_human=False)

        scores = build_day_vote_scores(
            player=player,
            candidates=[2, 3],
            current_votes={},
            claims={},
            logs=[],
            day_count=1,
            total_players=6,
            get_neighbor_triplet=lambda seat: [seat - 1, seat, seat + 1],
            alive_wolf_seats=[2],
        )

        self.assertLess(scores[2], scores[3])


if __name__ == "__main__":
    unittest.main()
