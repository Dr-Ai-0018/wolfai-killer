import asyncio
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game_human import submit_human_action_response, wait_for_human_action


class DummyEvent:
    def __init__(self):
        self._event = asyncio.Event()

    def clear(self):
        self._event.clear()

    def set(self):
        self._event.set()

    async def wait(self):
        await self._event.wait()


class HumanActionEngineStub:
    def __init__(self):
        self.waiting_for_human = None
        self.human_action_type = None
        self.human_action_options = {}
        self.human_response = None
        self.human_response_event = DummyEvent()
        self.logs = []
        self.emits = []
        self.state_emits = 0

    async def emit_state(self):
        self.state_emits += 1

    async def emit(self, event, data, to_seat=None):
        self.emits.append({"event": event, "data": data, "to_seat": to_seat})

    def add_log(self, log_type, content, seat=None):
        self.logs.append({"type": log_type, "content": content, "seat": seat})


class GameHumanTests(unittest.IsolatedAsyncioTestCase):
    async def test_wait_for_human_action_returns_submitted_response(self):
        engine = HumanActionEngineStub()

        async def submit_later():
            await asyncio.sleep(0)
            engine.human_response = {"target": 3}
            engine.human_response_event.set()

        task = asyncio.create_task(submit_later())
        response = await wait_for_human_action(engine, 1, "vote", {"candidates": [2, 3]}, timeout=1)
        await task

        self.assertEqual(response, {"target": 3})
        self.assertEqual(engine.state_emits, 2)
        self.assertEqual(engine.emits[0]["event"], "action_required")
        self.assertIsNone(engine.waiting_for_human)
        self.assertEqual(engine.human_action_options, {})

    async def test_wait_for_human_action_logs_timeout(self):
        engine = HumanActionEngineStub()

        response = await wait_for_human_action(engine, 2, "speech", {"message": "请发言"}, timeout=0)

        self.assertIsNone(response)
        self.assertTrue(any("超时，自动跳过" in log["content"] for log in engine.logs))
        self.assertEqual(engine.state_emits, 2)

    def test_submit_human_action_response_validates_waiting_seat(self):
        engine = HumanActionEngineStub()
        engine.waiting_for_human = 4

        self.assertFalse(submit_human_action_response(engine, 3, {"content": "skip"}))
        self.assertTrue(submit_human_action_response(engine, 4, {"content": "ok"}))
        self.assertEqual(engine.human_response, {"content": "ok"})


if __name__ == "__main__":
    unittest.main()
