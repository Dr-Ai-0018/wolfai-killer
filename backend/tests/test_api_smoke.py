import importlib.util
import os
import pathlib
import sys
import tempfile
import time
import unittest

from fastapi.testclient import TestClient


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

APP_PATH = ROOT / "app.py"
SPEC = importlib.util.spec_from_file_location("wolf_backend_app_smoke", APP_PATH)
APPFILE = importlib.util.module_from_spec(SPEC)
sys.modules["wolf_backend_app_smoke"] = APPFILE
assert SPEC.loader is not None
SPEC.loader.exec_module(APPFILE)
GAME_ENGINE_MODULE = sys.modules["game_engine"]


class ApiSmokeTests(unittest.TestCase):
    def setUp(self):
        APPFILE.game_manager.games.clear()
        APPFILE.game_manager.connections.clear()
        self.client = TestClient(APPFILE.app)
        self.original_admin_password = os.environ.get("WEREWOLF_ADMIN_PASSWORD")
        self.original_jwt_secret = os.environ.get("WEREWOLF_JWT_SECRET")
        os.environ["WEREWOLF_ADMIN_PASSWORD"] = "admin-smoke-pass"
        os.environ["WEREWOLF_JWT_SECRET"] = "smoke-jwt-secret"

    def tearDown(self):
        self.client.close()
        if self.original_admin_password is None:
            os.environ.pop("WEREWOLF_ADMIN_PASSWORD", None)
        else:
            os.environ["WEREWOLF_ADMIN_PASSWORD"] = self.original_admin_password
        if self.original_jwt_secret is None:
            os.environ.pop("WEREWOLF_JWT_SECRET", None)
        else:
            os.environ["WEREWOLF_JWT_SECRET"] = self.original_jwt_secret

    def test_root_and_config_endpoints(self):
        root = self.client.get("/")
        self.assertEqual(root.status_code, 200)
        self.assertEqual(root.json()["name"], "月夜狼人杀接口")

        roles = self.client.get("/api/config/roles")
        self.assertEqual(roles.status_code, 200)
        self.assertIsInstance(roles.json(), list)
        self.assertTrue(len(roles.json()) > 0)

        personalities = self.client.get("/api/config/personalities")
        self.assertEqual(personalities.status_code, 200)
        self.assertIsInstance(personalities.json(), list)
        self.assertTrue(len(personalities.json()) > 0)

        models = self.client.get("/api/config/models")
        self.assertEqual(models.status_code, 200)
        self.assertIsInstance(models.json(), list)

    def test_create_game_and_read_basic_views(self):
        payload = {
            "human_seats": [1],
            "total_players": 5,
            "num_wolves": 1,
            "role_config": {
                "WOLF": 1,
                "SEER": 1,
                "WITCH": 1,
                "HUNTER": 1,
                "VILLAGER": 1,
            },
            "random_models": False,
            "seat_model_map": {
                "1": "gpt-5.4-mini",
                "2": "gpt-5.4-mini",
                "3": "gpt-5.4-mini",
                "4": "gpt-5.4-mini",
                "5": "gpt-5.4-mini",
            },
            "god_mode": {"enabled": True, "password": "smoke-pass"},
        }

        created = self.client.post("/api/game/create", json=payload)
        self.assertEqual(created.status_code, 200)
        game_id = created.json()["game_id"]

        status = self.client.get(f"/api/game/{game_id}/status")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["phase"], "waiting")

        players = self.client.get(f"/api/game/{game_id}/players")
        self.assertEqual(players.status_code, 200)
        self.assertEqual(len(players.json()), 5)

        player_view = self.client.get(f"/api/game/{game_id}/player/1")
        self.assertEqual(player_view.status_code, 200)
        self.assertEqual(player_view.json()["seat"], 1)
        self.assertIn("role", player_view.json())

        logs = self.client.get(f"/api/game/{game_id}/log?limit=20")
        self.assertEqual(logs.status_code, 200)
        self.assertIn("logs", logs.json())

        god_verify = self.client.post(
            f"/api/game/{game_id}/god-mode/verify",
            json={"password": "smoke-pass"},
        )
        self.assertEqual(god_verify.status_code, 200)
        self.assertTrue(god_verify.json()["success"])

        phantom_actions = self.client.get(f"/api/game/{game_id}/phantom-actions")
        self.assertEqual(phantom_actions.status_code, 200)

    def test_create_game_setup_tracks_total_players_for_runtime_scoring(self):
        payload = {
            "preset_id": "lovers_7p",
            "human_seats": [1],
            "random_models": False,
            "seat_model_map": {
                "1": "gpt-5.4-mini",
                "2": "gpt-5.4-mini",
                "3": "gpt-5.4-mini",
                "4": "gpt-5.4-mini",
                "5": "gpt-5.4-mini",
                "6": "gpt-5.4-mini",
                "7": "gpt-5.4-mini",
            },
            "god_mode": {"enabled": True, "password": "smoke-pass"},
        }

        created = self.client.post("/api/game/create", json=payload)
        self.assertEqual(created.status_code, 200)
        game_id = created.json()["game_id"]
        engine = APPFILE.game_manager.get_game(game_id)

        self.assertIsNotNone(engine)
        self.assertEqual(engine.total_players, 7)
        self.assertEqual(len(engine.players), 7)

    def test_stats_endpoints(self):
        overview = self.client.get("/api/stats/overview")
        self.assertEqual(overview.status_code, 200)
        self.assertIn("total_games", overview.json())

        detailed = self.client.get("/api/stats/detailed")
        self.assertEqual(detailed.status_code, 200)

        role_stats = self.client.get("/api/stats/roles")
        self.assertEqual(role_stats.status_code, 200)

        personality_stats = self.client.get("/api/stats/personalities")
        self.assertEqual(personality_stats.status_code, 200)

        model_stats = self.client.get("/api/stats/models")
        self.assertEqual(model_stats.status_code, 200)

        history = self.client.get("/api/stats/history?page=1&per_page=5")
        self.assertEqual(history.status_code, 200)
        self.assertIn("games", history.json())

    def test_admin_auth_flow_config_and_fetch_models(self):
        check = self.client.get("/api/admin/check")
        self.assertEqual(check.status_code, 200)
        self.assertTrue(check.json()["configured"])

        wrong_login = self.client.post("/api/admin/login", json={"password": "wrong-pass"})
        self.assertEqual(wrong_login.status_code, 403)

        login = self.client.post("/api/admin/login", json={"password": "admin-smoke-pass"})
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.json()["success"])
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        verify = self.client.get("/api/admin/verify", headers=headers)
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.json()["valid"])

        config_before = self.client.get("/api/admin/config", headers=headers)
        self.assertEqual(config_before.status_code, 200)
        self.assertIn("model_ids", config_before.json())

        config_path = ROOT / "config.yaml"
        original_config = config_path.read_text(encoding="utf-8")
        original_set_key = APPFILE.set_key

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_env = pathlib.Path(tmpdir) / ".env"
            temp_env.write_text("", encoding="utf-8")

            def fake_set_key(path, key, value):
                return str(temp_env), key, value

            APPFILE.set_key = fake_set_key
            try:
                update = self.client.post(
                    "/api/admin/config",
                    json={
                        "api_url": "https://example.com/v1",
                        "api_key": "sk-smoke",
                        "model_ids": ["gpt-5.4-mini", "gpt-5.2"],
                    },
                    headers=headers,
                )
                self.assertEqual(update.status_code, 200)
                self.assertTrue(update.json()["success"])
            finally:
                config_path.write_text(original_config, encoding="utf-8")
                APPFILE.set_key = original_set_key
                APPFILE.game_manager.load_config()

        refresh = self.client.post("/api/admin/refresh", headers=headers)
        self.assertEqual(refresh.status_code, 200)
        self.assertTrue(refresh.json()["success"])
        refreshed_token = refresh.json()["access_token"]
        refreshed_headers = {"Authorization": f"Bearer {refreshed_token}"}

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"data": [{"id": "gpt-5.4-mini"}, {"id": "gpt-5.2"}]}

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url, headers=None):
                return FakeResponse()

        original_async_client = APPFILE.httpx.AsyncClient
        APPFILE.httpx.AsyncClient = FakeAsyncClient
        try:
            fetched = self.client.post(
                "/api/admin/fetch-models",
                json={"api_url": "https://example.com", "api_key": "sk-fetch"},
                headers=refreshed_headers,
            )
            self.assertEqual(fetched.status_code, 200)
            self.assertTrue(fetched.json()["success"])
            self.assertEqual(fetched.json()["model_ids"], ["gpt-5.4-mini", "gpt-5.2"])
        finally:
            APPFILE.httpx.AsyncClient = original_async_client

    def test_websocket_connect_ping_and_action(self):
        payload = {
            "human_seats": [1],
            "total_players": 5,
            "num_wolves": 1,
            "role_config": {
                "WOLF": 1,
                "SEER": 1,
                "WITCH": 1,
                "HUNTER": 1,
                "VILLAGER": 1,
            },
            "random_models": False,
            "seat_model_map": {
                "1": "gpt-5.4-mini",
                "2": "gpt-5.4-mini",
                "3": "gpt-5.4-mini",
                "4": "gpt-5.4-mini",
                "5": "gpt-5.4-mini",
            },
        }
        created = self.client.post("/api/game/create", json=payload)
        self.assertEqual(created.status_code, 200)
        game_id = created.json()["game_id"]
        engine = APPFILE.game_manager.get_game(game_id)
        assert engine is not None

        captured_actions = []

        def fake_submit_human_action(seat, data):
            captured_actions.append((seat, data))
            return True

        engine.waiting_for_human = 1
        engine.human_action_type = "speech"
        engine.human_action_options = {"candidates": [2, 3]}
        engine.submit_human_action = fake_submit_human_action

        with self.client.websocket_connect(f"/ws/{game_id}/1") as websocket:
            connected = websocket.receive_json()
            self.assertEqual(connected["event"], "connected")
            self.assertEqual(connected["data"]["seat"], 1)
            self.assertEqual(connected["data"]["game_state"]["waiting_for_human"], 1)

            websocket.send_json({"type": "ping"})
            pong = websocket.receive_json()
            self.assertEqual(pong["event"], "pong")

            websocket.send_json({"type": "action", "data": {"content": "我是1号，先听发言。"}})
            received = websocket.receive_json()
            self.assertEqual(received["event"], "action_received")
            self.assertTrue(received["data"]["success"])

        self.assertEqual(captured_actions, [(1, {"content": "我是1号，先听发言。"})])

    def test_full_game_flow_reaches_end_and_records_history(self):
        payload = {
            "human_seats": [],
            "total_players": 4,
            "num_wolves": 1,
            "role_config": {
                "WOLF": 1,
                "SEER": 1,
                "VILLAGER": 2,
            },
            "random_models": False,
            "seat_model_map": {
                "1": "gpt-5.4-mini",
                "2": "gpt-5.4-mini",
                "3": "gpt-5.4-mini",
                "4": "gpt-5.4-mini",
            },
        }

        created = self.client.post("/api/game/create", json=payload)
        self.assertEqual(created.status_code, 200)
        game_id = created.json()["game_id"]
        engine = APPFILE.game_manager.get_game(game_id)
        assert engine is not None

        original_sleep = GAME_ENGINE_MODULE.asyncio.sleep
        original_wolf = engine.generate_ai_wolf_action
        original_seer = engine.generate_ai_seer_action
        original_speech = engine.generate_ai_speech
        original_vote = engine.generate_ai_vote

        async def fast_sleep(_seconds):
            return None

        async def fake_wolf_action(_wolves, candidates):
            non_wolves = [seat for seat in candidates if engine.players[seat].camp != GAME_ENGINE_MODULE.Camp.WOLF]
            seer_targets = [seat for seat in non_wolves if engine.players[seat].role == GAME_ENGINE_MODULE.Role.SEER]
            return seer_targets[0] if seer_targets else (non_wolves[0] if non_wolves else None)

        async def fake_seer_action(_seer, candidates):
            wolves = [seat for seat in candidates if engine.players[seat].camp == GAME_ENGINE_MODULE.Camp.WOLF]
            return wolves[0] if wolves else (candidates[0] if candidates else None)

        async def fake_speech(player):
            if player.role == GAME_ENGINE_MODULE.Role.SEER:
                wolf_seats = [seat for seat, result in player.seer_results.items() if result == "狼人"]
                if wolf_seats:
                    return f"我是{player.seat}号，身份是预言家，我昨晚查了{wolf_seats[0]}号是狼人，今天我会投这个位置。"
                return f"我是{player.seat}号，身份是预言家，我今天先听发言，但会优先找狼。"
            if player.camp == GAME_ENGINE_MODULE.Camp.WOLF:
                good_targets = [seat for seat, other in engine.players.items() if other.alive and seat != player.seat and other.camp != GAME_ENGINE_MODULE.Camp.WOLF]
                target = good_targets[0] if good_targets else 1
                return f"我是{player.seat}号，我目前更怀疑{target}号。"
            wolf_seats = [seat for seat, other in engine.players.items() if other.alive and other.camp == GAME_ENGINE_MODULE.Camp.WOLF]
            target = wolf_seats[0] if wolf_seats else 1
            return f"我是{player.seat}号，我这轮先站边投{target}号。"

        async def fake_vote(player, candidates, _current_votes):
            if player.camp == GAME_ENGINE_MODULE.Camp.WOLF:
                good_targets = [seat for seat in candidates if engine.players[seat].camp != GAME_ENGINE_MODULE.Camp.WOLF]
                return good_targets[0] if good_targets else candidates[0]
            wolf_targets = [seat for seat in candidates if engine.players[seat].camp == GAME_ENGINE_MODULE.Camp.WOLF]
            return wolf_targets[0] if wolf_targets else candidates[0]

        GAME_ENGINE_MODULE.asyncio.sleep = fast_sleep
        engine.generate_ai_wolf_action = fake_wolf_action
        engine.generate_ai_seer_action = fake_seer_action
        engine.generate_ai_speech = fake_speech
        engine.generate_ai_vote = fake_vote

        try:
            started = self.client.post(f"/api/game/{game_id}/start")
            self.assertEqual(started.status_code, 200)
            self.assertTrue(started.json()["success"])

            deadline = time.time() + 5
            final_status = None
            while time.time() < deadline:
                status = self.client.get(f"/api/game/{game_id}/status")
                self.assertEqual(status.status_code, 200)
                final_status = status.json()
                if final_status["phase"] == "ended":
                    break
                time.sleep(0.05)

            assert final_status is not None
            self.assertEqual(final_status["phase"], "ended")
            self.assertEqual(final_status["winner"], "好人阵营")

            detail = self.client.get(f"/api/stats/game/{game_id}")
            self.assertEqual(detail.status_code, 200)
            detail_json = detail.json()
            self.assertEqual(detail_json["winner_camp"], "好人阵营")
            self.assertEqual(detail_json["game_id"], game_id)
            self.assertTrue(any(log["type"] == "end" for log in detail_json.get("public_logs", [])))

            phantom = self.client.get(f"/api/game/{game_id}/phantom-actions")
            self.assertEqual(phantom.status_code, 200)
            self.assertTrue(phantom.json()["available"])
        finally:
            GAME_ENGINE_MODULE.asyncio.sleep = original_sleep
            engine.generate_ai_wolf_action = original_wolf
            engine.generate_ai_seer_action = original_seer
            engine.generate_ai_speech = original_speech
            engine.generate_ai_vote = original_vote


if __name__ == "__main__":
    unittest.main()
