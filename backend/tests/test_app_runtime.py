from __future__ import annotations

import os
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from server import app as app_module  # noqa: E402
from server import session as session_module  # noqa: E402
from server.schemas import CoordinateModel, MoveRequest  # noqa: E402


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


class AppRuntimeTests(unittest.TestCase):
    def test_create_app_uses_explicit_cors_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, _patched_env(
            CHECKERS_STATE_FILE=str(Path(temp_dir) / "session_store.json"),
            CHECKERS_ALLOWED_ORIGINS="https://frontend.example,https://preview.example",
        ):
            app = app_module.create_app()

        self.assertTrue(app.user_middleware, "Expected CORSMiddleware to be installed.")
        cors = app.user_middleware[0]
        self.assertEqual(cors.kwargs["allow_origins"], ["https://frontend.example", "https://preview.example"])
        self.assertTrue(cors.kwargs["allow_credentials"])

    def test_default_allowed_origins_do_not_use_wildcard(self) -> None:
        with _patched_env(CHECKERS_ALLOWED_ORIGINS=""):
            self.assertNotIn("*", app_module._allowed_origins_from_env())

    def test_session_store_persists_sessions_and_evaluations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "session_store.json"
            store = app_module._SessionStore(state_file=state_file, max_sessions=5, session_ttl_seconds=3600)
            session_id, session, created = store.get_or_create(None)

            self.assertTrue(created)
            session.make_move(
                MoveRequest(
                    start=CoordinateModel(row=5, col=0),
                    steps=[CoordinateModel(row=4, col=1)],
                )
            )

            state = session_module.EvaluationState(
                evaluation_id="eval-1",
                config={
                    "variant": "british",
                    "drawPolicy": "half",
                    "white": {"type": "minimax", "depth": 2},
                    "black": {"type": "mcts", "iterations": 10},
                },
                total_games=1,
                results=[
                    session_module.EvaluationResult(
                        index=1,
                        winner="white",
                        move_count=1,
                        duration_seconds=0.2,
                        avg_move_time_white=0.1,
                        avg_move_time_black=0.0,
                        starting_color="white",
                    )
                ],
                running=False,
                stop_event=threading.Event(),
            )
            with session._evaluation_lock:
                session._evaluations[state.evaluation_id] = state
            session._persist_evaluations()

            restored_store = app_module._SessionStore(state_file=state_file, max_sessions=5, session_ttl_seconds=3600)
            restored_id, restored_session, restored_created = restored_store.get_or_create(session_id)

        self.assertFalse(restored_created)
        self.assertEqual(restored_id, session_id)
        self.assertEqual(restored_session.serialize()["moveCount"], 1)
        self.assertIn("eval-1", restored_session._evaluations)

    def test_session_store_access_updates_recency_and_reuses_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "session_store.json"
            store = app_module._SessionStore(state_file=state_file, max_sessions=2, session_ttl_seconds=3600)
            session_id, _, _ = store.get_or_create(None)
            same_id, _, created = store.get_or_create(session_id)

        self.assertEqual(same_id, session_id)
        self.assertFalse(created)

    def test_session_store_merges_sessions_across_store_instances(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "session_store.json"
            store_a = app_module._SessionStore(state_file=state_file, max_sessions=5, session_ttl_seconds=3600)
            store_b = app_module._SessionStore(state_file=state_file, max_sessions=5, session_ttl_seconds=3600)

            session_a_id, session_a, _ = store_a.get_or_create(None)
            session_a.make_move(
                MoveRequest(
                    start=CoordinateModel(row=5, col=0),
                    steps=[CoordinateModel(row=4, col=1)],
                )
            )
            session_b_id, _, _ = store_b.get_or_create(None)

            store_c = app_module._SessionStore(state_file=state_file, max_sessions=5, session_ttl_seconds=3600)
            restored_a_id, restored_a, created_a = store_c.get_or_create(session_a_id)
            restored_b_id, _, created_b = store_c.get_or_create(session_b_id)

        self.assertFalse(created_a)
        self.assertFalse(created_b)
        self.assertEqual(restored_a_id, session_a_id)
        self.assertEqual(restored_b_id, session_b_id)
        self.assertEqual(restored_a.serialize()["moveCount"], 1)

    def test_session_store_resumes_running_evaluations_on_restore(self) -> None:
        resumed = threading.Event()
        finished = threading.Event()

        def fake_run(self, state):  # noqa: ANN001
            try:
                resumed.set()
                with self._evaluation_lock:
                    state.results.append(
                        session_module.EvaluationResult(
                            index=state.total_games,
                            winner="white",
                            move_count=1,
                            duration_seconds=0.1,
                            avg_move_time_white=0.1,
                            avg_move_time_black=0.0,
                            starting_color="white",
                        )
                    )
                    state.running = False
                    state.thread = None
                self._persist_evaluations()
            finally:
                finished.set()

        with tempfile.TemporaryDirectory() as temp_dir, _patch_attr(session_module.GameSession, "_run_evaluation", fake_run):
            state_file = Path(temp_dir) / "session_store.json"
            store = app_module._SessionStore(state_file=state_file, max_sessions=5, session_ttl_seconds=3600)
            session_id, session, _ = store.get_or_create(None)
            state = session_module.EvaluationState(
                evaluation_id="eval-running",
                config={
                    "variant": "british",
                    "drawPolicy": "half",
                    "white": {"type": "minimax", "depth": 1},
                    "black": {"type": "mcts", "iterations": 1},
                },
                total_games=1,
                results=[],
                running=True,
                stop_event=threading.Event(),
            )
            with session._evaluation_lock:
                session._evaluations[state.evaluation_id] = state
            session._persist_evaluations()

            restored_store = app_module._SessionStore(state_file=state_file, max_sessions=5, session_ttl_seconds=3600)
            restored_id, restored_session, created = restored_store.get_or_create(session_id)
            self.assertTrue(resumed.wait(timeout=2.0), "Persisted evaluation did not resume after restore.")
            self.assertTrue(finished.wait(timeout=2.0), "Resumed evaluation did not finish cleanly after restore.")

        self.assertFalse(created)
        self.assertEqual(restored_id, session_id)
        payload = restored_session.get_evaluation_status("eval-running")
        self.assertFalse(payload["running"])
        self.assertEqual(payload["completedGames"], 1)

    def test_session_store_round_trips_new_evaluation_timing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "session_store.json"
            store = app_module._SessionStore(state_file=state_file, max_sessions=5, session_ttl_seconds=3600)
            session_id, session, _ = store.get_or_create(None)
            state = session_module.EvaluationState(
                evaluation_id="eval-meta",
                config={
                    "variant": "british",
                    "drawPolicy": "half",
                    "moveCap": 333,
                    "maxDurationSeconds": 90,
                    "white": {"type": "minimax", "depth": 1},
                    "black": {"type": "mcts", "iterations": 1},
                },
                total_games=4,
                results=[],
                running=False,
                stop_event=threading.Event(),
                started_at_epoch=100.0,
                updated_at_epoch=120.0,
                deadline_at_epoch=190.0,
                stop_reason="time_budget",
                completed_at_epoch=121.0,
                error_message=None,
            )
            with session._evaluation_lock:
                session._evaluations[state.evaluation_id] = state
            session._persist_evaluations()

            restored_store = app_module._SessionStore(state_file=state_file, max_sessions=5, session_ttl_seconds=3600)
            _, restored_session, _ = restored_store.get_or_create(session_id)

        payload = restored_session.get_evaluation_status("eval-meta")
        self.assertEqual(payload["metadata"]["moveCap"], 333)
        self.assertEqual(payload["metadata"]["maxDurationSeconds"], 90)
        self.assertEqual(payload["startedAtEpoch"], 100.0)
        self.assertEqual(payload["updatedAtEpoch"], 120.0)
        self.assertEqual(payload["deadlineAtEpoch"], 190.0)
        self.assertEqual(payload["completedAtEpoch"], 121.0)
        self.assertEqual(payload["stopReason"], "time_budget")

    def test_corrupted_state_file_raises_runtime_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "session_store.json"
            state_file.write_text("{not valid json", encoding="utf-8")

            with self.assertRaises(RuntimeError):
                app_module._SessionStore(state_file=state_file, max_sessions=5, session_ttl_seconds=3600)


if __name__ == "__main__":
    unittest.main()
