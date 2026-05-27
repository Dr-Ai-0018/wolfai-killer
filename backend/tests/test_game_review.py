import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_review import build_day_summary, build_public_claim_summary, extract_speech_meta


class GameReviewHelpersTests(unittest.TestCase):
    def test_extract_speech_meta_detects_claim_and_mentions(self):
        meta = extract_speech_meta("我是3号，身份是预言家。今天我重点看5号和7号。")

        self.assertEqual(meta["claimed_role"], "预言家")
        self.assertEqual(meta["mentioned_seats"], [3, 5, 7])

    def test_build_public_claim_summary_only_counts_alive_public_speakers(self):
        logs = [
            {"type": "speech", "is_public": True, "seat": 1, "meta": {"claimed_role": "预言家"}},
            {"type": "speech", "is_public": True, "seat": 2, "meta": {"claimed_role": "女巫"}},
            {"type": "speech", "is_public": False, "seat": 3, "meta": {"claimed_role": "猎人"}},
            {"type": "speech", "is_public": True, "seat": 4, "meta": {"claimed_role": "守卫"}},
        ]

        claims = build_public_claim_summary(logs, alive_seats=[1, 2])

        self.assertEqual(claims, {"预言家": [1], "女巫": [2]})

    def test_build_day_summary_aggregates_votes_mentions_and_claims(self):
        logs = [
            {
                "type": "speech",
                "is_public": True,
                "seat": 1,
                "day": 2,
                "meta": {"claimed_role": "预言家", "mentioned_seats": [2, 3]},
            },
            {
                "type": "speech",
                "is_public": True,
                "seat": 2,
                "day": 2,
                "meta": {"mentioned_seats": [3]},
            },
            {
                "type": "vote",
                "is_public": True,
                "seat": 1,
                "day": 2,
                "meta": {"voter": 1, "target": 3},
            },
            {
                "type": "vote",
                "is_public": True,
                "seat": 2,
                "day": 2,
                "meta": {"voter": 2, "target": 3},
            },
        ]

        summary = build_day_summary(logs, alive_seats=[1, 2, 3], day_count=2, phase="vote")

        self.assertEqual(summary["claims"], {"预言家": [1]})
        self.assertEqual(summary["vote_map"], {1: 3, 2: 3})
        self.assertEqual(summary["vote_counts"], {3: 2})
        self.assertEqual(summary["pressure_board"][0]["seat"], 3)
        self.assertEqual(summary["pressure_board"][0]["mentions"], 2)
        self.assertEqual(summary["pressure_board"][0]["votes"], 2)
