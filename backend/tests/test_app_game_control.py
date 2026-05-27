import pathlib
import sys
import unittest

from fastapi import HTTPException


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app_game_control import (
    pause_game_response,
    resume_game_response,
    start_game_response,
    submit_action_response,
)


class DummyEngine:
    def __init__(self, waiting_for_human=None, submit_result=True):
        self.waiting_for_human = waiting_for_human
        self.submit_result = submit_result
        self.pause_called = False
        self.resume_called = False
        self.submit_calls = []
        self.start_called = False

    async def start(self):
        self.start_called = True

    def pause(self):
        self.pause_called = True

    def resume(self):
        self.resume_called = True

    def submit_human_action(self, seat, action_data):
        self.submit_calls.append((seat, action_data))
        return self.submit_result


class DummyGameManager:
    def __init__(self, engine=None):
        self.engine = engine

    def get_game(self, _game_id: str):
        return self.engine


class AppGameControlTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_game_response_schedules_engine_start(self):
        engine = DummyEngine()
        scheduled = []

        def fake_create_task(coro):
            scheduled.append(coro)
            coro.close()
            return object()

        payload = await start_game_response(DummyGameManager(engine), "game-1", fake_create_task)

        self.assertEqual(payload, {"success": True, "message": "Game started"})
        self.assertEqual(len(scheduled), 1)

    async def test_pause_resume_and_submit_action_responses(self):
        engine = DummyEngine(waiting_for_human=3, submit_result=True)
        manager = DummyGameManager(engine)

        pause_payload = pause_game_response(manager, "game-1")
        resume_payload = resume_game_response(manager, "game-1")
        submit_payload = submit_action_response(manager, "game-1", {"target": 5})

        self.assertTrue(engine.pause_called)
        self.assertTrue(engine.resume_called)
        self.assertEqual(engine.submit_calls, [(3, {"target": 5})])
        self.assertEqual(pause_payload, {"success": True, "message": "Game paused"})
        self.assertEqual(resume_payload, {"success": True, "message": "对局已继续"})
        self.assertEqual(submit_payload, {"success": True})

    async def test_missing_game_still_raises_http_exception(self):
        with self.assertRaises(HTTPException):
            await start_game_response(DummyGameManager(None), "missing", lambda coro: coro.close())
        with self.assertRaises(HTTPException):
            pause_game_response(DummyGameManager(None), "missing")


if __name__ == "__main__":
    unittest.main()
