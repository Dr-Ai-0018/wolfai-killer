import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_day import build_human_speech_options, build_speech_log, resolve_human_speech


class GameDayTests(unittest.TestCase):
    def test_build_human_speech_options(self):
        self.assertEqual(build_human_speech_options(), {"message": "请发言", "timeout": 60})

    def test_resolve_human_speech_with_missing_response(self):
        self.assertEqual(resolve_human_speech(None), "（未发言）")

    def test_resolve_human_speech_with_content(self):
        self.assertEqual(resolve_human_speech({"content": "我是2号，先听后置位。"}), "我是2号，先听后置位。")

    def test_build_speech_log_uses_meta_extractor(self):
        payload = build_speech_log(
            3,
            "我是3号，身份是预言家。",
            lambda speech: {"claimed_role": "预言家", "raw": speech},
        )

        self.assertEqual(payload["type"], "speech")
        self.assertEqual(payload["seat"], 3)
        self.assertEqual(payload["content"], "我是3号，身份是预言家。")
        self.assertEqual(payload["meta"], {"claimed_role": "预言家", "raw": "我是3号，身份是预言家。"})


if __name__ == "__main__":
    unittest.main()
