from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from server import app as app_module  # noqa: E402
from server import session as session_module  # noqa: E402


@contextmanager
def _patched_env(**updates: str):
    old = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def _patch_attr(obj, name: str, value):
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


class AppApiTests(unittest.TestCase):
    def test_board_request_sets_session_cookie(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _patched_env(
            CHECKERS_STATE_FILE=str(Path(temp_dir) / "session_store.json"),
        ):
            client = TestClient(app_module.create_app())
            response = client.get("/board")

        self.assertEqual(response.status_code, 200)
        self.assertIn("checkers_session_id", response.cookies)
        cookie_header = response.headers.get("set-cookie", "")
        self.assertIn("HttpOnly", cookie_header)
        self.assertIn("SameSite=lax", cookie_header)

    def test_same_cookie_reuses_session_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _patched_env(
            CHECKERS_STATE_FILE=str(Path(temp_dir) / "session_store.json"),
        ):
            client = TestClient(app_module.create_app())
            move_response = client.post(
                "/move",
                json={
                    "start": {"row": 5, "col": 0},
                    "steps": [{"row": 4, "col": 1}],
                },
            )
            board_response = client.get("/board")

        self.assertEqual(move_response.status_code, 200)
        self.assertEqual(board_response.status_code, 200)
        self.assertEqual(board_response.json()["moveCount"], 1)

    def test_invalid_move_returns_400(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _patched_env(
            CHECKERS_STATE_FILE=str(Path(temp_dir) / "session_store.json"),
        ):
            client = TestClient(app_module.create_app())
            response = client.post(
                "/move",
                json={
                    "start": {"row": 0, "col": 0},
                    "steps": [{"row": 1, "col": 1}],
                },
            )

        self.assertEqual(response.status_code, 400)

    def test_cors_preflight_returns_allowed_origin_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _patched_env(
            CHECKERS_STATE_FILE=str(Path(temp_dir) / "session_store.json"),
            CHECKERS_ALLOWED_ORIGINS="http://localhost:5173",
        ):
            client = TestClient(app_module.create_app())
            response = client.options(
                "/move",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "POST",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://localhost:5173")
        self.assertEqual(response.headers.get("access-control-allow-credentials"), "true")

    def test_evaluation_endpoints_round_trip(self) -> None:
        def fake_run(self, state):  # noqa: ANN001
            with self._evaluation_lock:
                state.results.append(
                    session_module.EvaluationResult(
                        index=1,
                        winner="white",
                        move_count=12,
                        duration_seconds=0.5,
                        avg_move_time_white=0.1,
                        avg_move_time_black=0.2,
                        starting_color="white",
                    )
                )
                state.running = False
                state.thread = None
                state.stop_reason = "completed_games"
                state.updated_at_epoch = state.started_at_epoch
            self._persist_evaluations()

        with tempfile.TemporaryDirectory() as temp_dir, _patched_env(
            CHECKERS_STATE_FILE=str(Path(temp_dir) / "session_store.json"),
        ), _patch_attr(session_module.GameSession, "_run_evaluation", fake_run):
            client = TestClient(app_module.create_app())
            start = client.post(
                "/evaluate/start",
                json={
                    "games": 1,
                    "variant": "british",
                    "moveCap": 320,
                    "maxDurationSeconds": 30,
                    "white": {"type": "minimax", "depth": 2},
                    "black": {"type": "mcts", "iterations": 10},
                },
            )
            self.assertEqual(start.status_code, 200)
            evaluation_id = start.json()["evaluationId"]

            status = client.get("/evaluate/status", params={"evaluation_id": evaluation_id})
            csv_results = client.get("/evaluate/results", params={"evaluation_id": evaluation_id, "format": "csv"})
            json_results = client.get("/evaluate/results", params={"evaluation_id": evaluation_id, "format": "json"})
            stop = client.post("/evaluate/stop", json={"evaluationId": evaluation_id})

        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["metadata"]["moveCap"], 320)
        self.assertEqual(status.json()["metadata"]["maxDurationSeconds"], 30)
        self.assertIn("stopReason", status.json())
        self.assertEqual(csv_results.status_code, 200)
        self.assertIn("stopReason", csv_results.text)
        self.assertEqual(json_results.status_code, 200)
        self.assertEqual(json_results.json()["evaluationId"], evaluation_id)
        self.assertEqual(stop.status_code, 200)

    def test_second_evaluation_start_is_rejected_while_first_is_running(self) -> None:
        release = threading.Event()
        started = threading.Event()

        def fake_run(self, state):  # noqa: ANN001
            started.set()
            release.wait(timeout=2.0)
            with self._evaluation_lock:
                state.running = False
                state.thread = None
                state.stop_reason = state.stop_reason or "completed_games"
                state.updated_at_epoch = state.started_at_epoch
            self._persist_evaluations()

        with tempfile.TemporaryDirectory() as temp_dir, _patched_env(
            CHECKERS_STATE_FILE=str(Path(temp_dir) / "session_store.json"),
        ), _patch_attr(session_module.GameSession, "_run_evaluation", fake_run):
            client = TestClient(app_module.create_app())
            first = client.post(
                "/evaluate/start",
                json={
                    "games": 5,
                    "variant": "british",
                    "white": {"type": "minimax", "depth": 2},
                    "black": {"type": "mcts", "iterations": 10},
                },
            )
            self.assertEqual(first.status_code, 200)
            self.assertTrue(started.wait(timeout=1.0))
            evaluation_id = first.json()["evaluationId"]

            second = client.post(
                "/evaluate/start",
                json={
                    "games": 5,
                    "variant": "british",
                    "white": {"type": "minimax", "depth": 2},
                    "black": {"type": "mcts", "iterations": 10},
                },
            )
            release.set()
            for _ in range(100):
                status = client.get("/evaluate/status", params={"evaluation_id": evaluation_id})
                if status.status_code == 200 and not status.json()["running"]:
                    break
                time.sleep(0.01)

        self.assertEqual(second.status_code, 400)
        self.assertIn("already running", second.json()["detail"])

    def test_evaluation_stop_marks_stop_reason_for_running_job(self) -> None:
        release = threading.Event()
        started = threading.Event()

        def fake_run(self, state):  # noqa: ANN001
            started.set()
            while not state.stop_event.is_set():
                if release.wait(timeout=0.01):
                    break
            with self._evaluation_lock:
                state.running = False
                state.thread = None
                state.updated_at_epoch = state.started_at_epoch
                state.completed_at_epoch = state.started_at_epoch
                state.stop_reason = state.stop_reason or "stopped_by_user"
            self._persist_evaluations()

        with tempfile.TemporaryDirectory() as temp_dir, _patched_env(
            CHECKERS_STATE_FILE=str(Path(temp_dir) / "session_store.json"),
        ), _patch_attr(session_module.GameSession, "_run_evaluation", fake_run):
            client = TestClient(app_module.create_app())
            start = client.post(
                "/evaluate/start",
                json={
                    "games": 5,
                    "variant": "british",
                    "white": {"type": "minimax", "depth": 2},
                    "black": {"type": "mcts", "iterations": 10},
                },
            )
            self.assertEqual(start.status_code, 200)
            self.assertTrue(started.wait(timeout=1.0))
            evaluation_id = start.json()["evaluationId"]

            stop = client.post("/evaluate/stop", json={"evaluationId": evaluation_id})
            release.set()

            status = client.get("/evaluate/status", params={"evaluation_id": evaluation_id})

        self.assertEqual(stop.status_code, 200)
        self.assertEqual(stop.json()["stopReason"], "stopped_by_user")
        self.assertEqual(status.status_code, 200)
        self.assertFalse(status.json()["running"])
        self.assertEqual(status.json()["stopReason"], "stopped_by_user")

    def test_evaluation_status_is_isolated_per_session(self) -> None:
        def fake_run(self, state):  # noqa: ANN001
            with self._evaluation_lock:
                state.results.append(
                    session_module.EvaluationResult(
                        index=1,
                        winner="black",
                        move_count=8,
                        duration_seconds=0.2,
                        avg_move_time_white=0.1,
                        avg_move_time_black=0.1,
                        starting_color="white",
                    )
                )
                state.running = False
                state.thread = None
                state.stop_reason = "completed_games"
                state.updated_at_epoch = state.started_at_epoch
            self._persist_evaluations()

        with tempfile.TemporaryDirectory() as temp_dir, _patched_env(
            CHECKERS_STATE_FILE=str(Path(temp_dir) / "session_store.json"),
        ), _patch_attr(session_module.GameSession, "_run_evaluation", fake_run):
            app = app_module.create_app()
            client_a = TestClient(app)
            client_b = TestClient(app)

            start = client_a.post(
                "/evaluate/start",
                json={
                    "games": 1,
                    "variant": "british",
                    "white": {"type": "minimax", "depth": 2},
                    "black": {"type": "mcts", "iterations": 10},
                },
            )
            self.assertEqual(start.status_code, 200)
            evaluation_id = start.json()["evaluationId"]

            other_status = client_b.get("/evaluate/status", params={"evaluation_id": evaluation_id})
            other_results = client_b.get("/evaluate/results", params={"evaluation_id": evaluation_id, "format": "json"})

        self.assertEqual(other_status.status_code, 404)
        self.assertEqual(other_results.status_code, 404)


if __name__ == "__main__":
    unittest.main()
