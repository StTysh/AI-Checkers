import sys
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path

from pydantic import ValidationError


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from ai.cancel import CancelledError  # noqa: E402
from core.player import PlayerController, PlayerKind  # noqa: E402
from server import session as session_module  # noqa: E402
from server.schemas import AIMoveRequest, ConfigRequest, EvaluationStartRequest, PerformAIMoveRequest, PlayerConfigPayload, VariantRequest  # noqa: E402
from core.board import Board  # noqa: E402
from core.pieces import Color, Man  # noqa: E402


@contextmanager
def _patch_attr(obj, name: str, value):
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


def _dummy_ai_controller(kind: PlayerKind, started: threading.Event, block: bool = False) -> PlayerController:
    def _policy(game, cancel_event=None):
        started.set()
        if block:
            while cancel_event is not None and not cancel_event.is_set():
                time.sleep(0.001)
            raise CancelledError()
        moves_map = game.board.getAllValidMoves(game.current_player)
        if not moves_map:
            return None
        piece = next(iter(moves_map.keys()))
        move = moves_map[piece][0]
        return (piece, move)

    return PlayerController(kind=kind, name="Dummy AI", policy=_policy)


class SessionOptionWiringTests(unittest.TestCase):
    def _make_evaluation_state(self, draw_policy: str | None) -> session_module.EvaluationState:
        state = session_module.EvaluationState(
            evaluation_id="eval-1",
            config={
                "variant": "british",
                "startPolicy": "alternate",
                "randomSeed": 7,
                "randomizeOpening": False,
                "randomizePlies": 0,
                "moveCap": 300,
                "experimentName": "demo",
                "notes": "test",
                "drawPolicy": draw_policy,
                "maxDurationSeconds": 60,
                "white": {"type": "minimax", "depth": 4},
                "black": {"type": "mcts", "iterations": 25},
            },
            total_games=3,
            results=[],
            running=False,
            stop_event=threading.Event(),
        )
        state.results.extend(
            [
                session_module.EvaluationResult(
                    index=1,
                    winner="white",
                    move_count=12,
                    duration_seconds=1.5,
                    avg_move_time_white=0.1,
                    avg_move_time_black=0.2,
                    starting_color="white",
                ),
                session_module.EvaluationResult(
                    index=2,
                    winner="white",
                    move_count=14,
                    duration_seconds=2.0,
                    avg_move_time_white=0.2,
                    avg_move_time_black=0.3,
                    starting_color="black",
                ),
                session_module.EvaluationResult(
                    index=3,
                    winner=None,
                    move_count=16,
                    duration_seconds=2.5,
                    avg_move_time_white=0.3,
                    avg_move_time_black=0.4,
                    starting_color="white",
                ),
            ]
        )
        return state

    def test_run_ai_move_payload_maps_minimax_fields(self) -> None:
        captured = {}
        started = threading.Event()

        def fake_create_minimax_controller(name: str, depth: int = 4, **kwargs):
            captured["name"] = name
            captured["depth"] = depth
            captured.update(kwargs)
            return _dummy_ai_controller(PlayerKind.MINIMAX, started)

        with _patch_attr(session_module, "create_minimax_controller", fake_create_minimax_controller):
            session = session_module.GameSession()
            payload = AIMoveRequest(
                algorithm="minimax",
                color="white",
                depth=5,
                alphaBeta=False,
                transposition=False,
                moveOrdering=True,
                deterministicOrdering=False,
                parallel=True,
                workers=1,
                persist=False,
                commitImmediately=False,
            )
            _ = session.run_ai_move(payload)

        self.assertTrue(started.is_set(), "Dummy Minimax policy did not run.")
        self.assertEqual(captured["depth"], 5)
        self.assertEqual(captured["use_alpha_beta"], False)
        self.assertEqual(captured["use_transposition"], False)
        self.assertEqual(captured["use_move_ordering"], True)
        self.assertEqual(captured["deterministic_ordering"], False)
        self.assertEqual(captured["use_parallel"], True)
        self.assertEqual(captured["workers"], 1)

    def test_run_ai_move_terminal_position_sets_winner(self) -> None:
        called = threading.Event()

        def fake_create_minimax_controller(*args, **kwargs):
            called.set()
            return _dummy_ai_controller(PlayerKind.MINIMAX, threading.Event())

        session = session_module.GameSession()
        board = Board.empty(8, turn=Color.WHITE)
        board.board[0][1] = Man(Color.WHITE, 0, 1)
        board.board[7][0] = Man(Color.BLACK, 7, 0)
        board.zobrist_hash = board.recompute_hash()
        session.game.board = board
        session.game.current_player = board.turn
        session.game.winner = None

        payload = AIMoveRequest(
            algorithm="minimax",
            color="white",
            depth=4,
            persist=False,
            commitImmediately=False,
        )

        with _patch_attr(session_module, "create_minimax_controller", fake_create_minimax_controller):
            resp = session.run_ai_move(payload)

        self.assertFalse(called.is_set(), "Controller should not run on terminal positions.")
        self.assertEqual(resp["winner"], "black")

    def test_configure_players_maps_mcts_fields(self) -> None:
        captured = {}
        started = threading.Event()

        def fake_create_mcts_controller(name: str, **kwargs):
            captured["name"] = name
            captured.update(kwargs)
            return _dummy_ai_controller(PlayerKind.MONTE_CARLO, started)

        with _patch_attr(session_module, "create_mcts_controller", fake_create_mcts_controller):
            session = session_module.GameSession()
            payload = ConfigRequest(
                white=PlayerConfigPayload(
                    type="mcts",
                    iterations=321,
                    rolloutDepth=77,
                    explorationConstant=0.75,
                    randomSeed=42,
                    mctsParallel=True,
                    mctsWorkers=1,
                    rolloutPolicy="heuristic",
                    guidanceDepth=1,
                    rolloutCutoffDepth=10,
                    leafEvaluation="heuristic_eval",
                    mctsTransposition=True,
                    mctsTranspositionMaxEntries=12345,
                    progressiveWidening=True,
                    pwK=1.8,
                    pwAlpha=0.55,
                    progressiveBias=True,
                    pbWeight=0.9,
                )
            )
            _ = session.configure_players(payload)

        self.assertFalse(started.is_set(), "configure_players should not run the controller policy.")
        self.assertEqual(captured["iterations"], 321)
        self.assertEqual(captured["rollout_depth"], 77)
        self.assertEqual(captured["exploration_constant"], 0.75)
        self.assertEqual(captured["random_seed"], 42)
        self.assertEqual(captured["use_parallel"], True)
        self.assertEqual(captured["workers"], 1)
        self.assertEqual(captured["rollout_policy"], "heuristic")
        self.assertEqual(captured["guidance_depth"], 1)
        self.assertEqual(captured["rollout_cutoff_depth"], 10)
        self.assertEqual(captured["leaf_evaluation"], "heuristic_eval")
        self.assertEqual(captured["use_transposition"], True)
        self.assertEqual(captured["transposition_max_entries"], 12345)
        self.assertEqual(captured["progressive_widening"], True)
        self.assertEqual(captured["pw_k"], 1.8)
        self.assertEqual(captured["pw_alpha"], 0.55)
        self.assertEqual(captured["progressive_bias"], True)
        self.assertEqual(captured["pb_weight"], 0.9)

    def test_reset_and_variant_cancel_inflight_ai(self) -> None:
        started = threading.Event()

        def fake_create_minimax_controller(name: str, depth: int = 4, **kwargs):
            return _dummy_ai_controller(PlayerKind.MINIMAX, started, block=True)

        with _patch_attr(session_module, "create_minimax_controller", fake_create_minimax_controller):
            session = session_module.GameSession()
            payload = AIMoveRequest(
                algorithm="minimax",
                color="white",
                depth=12,
                persist=False,
                commitImmediately=False,
            )

            def start_ai_thread() -> tuple[threading.Thread, list[BaseException]]:
                started.clear()
                errors: list[BaseException] = []

                def worker() -> None:
                    try:
                        session.run_ai_move(payload)
                    except BaseException as exc:  # noqa: BLE001
                        errors.append(exc)

                thread = threading.Thread(target=worker, daemon=True)
                thread.start()
                self.assertTrue(started.wait(timeout=1.0), "AI policy did not start.")
                return thread, errors

            thread, errors = start_ai_thread()
            t0 = time.perf_counter()
            _ = session.configure_players(
                ConfigRequest(white=PlayerConfigPayload(type="minimax", depth=2, alphaBeta=True))
            )
            dt = time.perf_counter() - t0
            self.assertLess(dt, 0.5, "configure_players took too long while AI was thinking.")
            thread.join(timeout=2.0)
            self.assertFalse(thread.is_alive(), "run_ai_move thread did not stop after config change.")
            self.assertFalse(errors, f"run_ai_move raised unexpected exception: {errors!r}")

            thread, errors = start_ai_thread()
            t0 = time.perf_counter()
            _ = session.set_variant(VariantRequest(variant="international"))
            dt = time.perf_counter() - t0
            self.assertLess(dt, 0.5, "set_variant took too long while AI was thinking.")
            thread.join(timeout=2.0)
            self.assertFalse(thread.is_alive(), "run_ai_move thread did not stop after variant change.")
            self.assertFalse(errors, f"run_ai_move raised unexpected exception: {errors!r}")

    def test_worker_count_is_clamped_to_cpu(self) -> None:
        captured = {}

        def fake_create_minimax_controller(name: str, depth: int = 4, **kwargs):
            captured["workers"] = kwargs.get("workers")
            return _dummy_ai_controller(PlayerKind.MINIMAX, threading.Event())

        with _patch_attr(session_module, "create_minimax_controller", fake_create_minimax_controller):
            session = session_module.GameSession()
            payload = AIMoveRequest(
                algorithm="minimax",
                color="white",
                depth=3,
                parallel=True,
                workers=64,
                persist=False,
                commitImmediately=False,
            )
            _ = session.run_ai_move(payload)

        cpu_total = session_module.os.cpu_count() or 1
        recommended = max(1, cpu_total - 2)
        self.assertLessEqual(captured["workers"], recommended)

    def test_perform_ai_move_increments_state_version(self) -> None:
        started = threading.Event()

        def fake_create_minimax_controller(name: str, depth: int = 4, **kwargs):
            return _dummy_ai_controller(PlayerKind.MINIMAX, started)

        with _patch_attr(session_module, "create_minimax_controller", fake_create_minimax_controller):
            session = session_module.GameSession()
            pending = session.run_ai_move(
                AIMoveRequest(
                    algorithm="minimax",
                    color="white",
                    depth=3,
                    persist=False,
                    commitImmediately=False,
                )
            )

        self.assertIsNotNone(pending["pendingAiMoves"]["white"])
        version_before = session._state_version

        payload = session.perform_ai_move(PerformAIMoveRequest(color="white"))

        self.assertEqual(session._state_version, version_before + 1)
        self.assertIsNone(payload["pendingAiMoves"]["white"])
        self.assertEqual(payload["moveCount"], 1)

    def test_evaluation_request_rejects_human_players(self) -> None:
        with self.assertRaises(ValidationError):
            EvaluationStartRequest(
                games=1,
                variant="british",
                white={"type": "human"},
                black={"type": "mcts"},
            )

    def test_evaluation_draw_policy_affects_summary_rates(self) -> None:
        session = session_module.GameSession()

        for policy, expected_white, expected_black in (
            ("zero", 2 / 3, 0.0),
            ("half", 5 / 6, 1 / 6),
            ("ignore", 1.0, 0.0),
        ):
            with self.subTest(policy=policy):
                state = self._make_evaluation_state(policy)
                payload = session._evaluation_status_payload(state)
                self.assertEqual(payload["score"]["whiteWins"], 2)
                self.assertEqual(payload["score"]["blackWins"], 0)
                self.assertEqual(payload["score"]["draws"], 1)
                self.assertAlmostEqual(payload["summary"]["winRateWhite"], expected_white)
                self.assertAlmostEqual(payload["summary"]["winRateBlack"], expected_black)
                self.assertEqual(payload["metadata"]["drawPolicy"], policy)

    def test_evaluation_status_includes_time_budget_fields(self) -> None:
        session = session_module.GameSession()
        state = self._make_evaluation_state("half")

        payload = session._evaluation_status_payload(state)

        self.assertEqual(payload["metadata"]["maxDurationSeconds"], 60)
        self.assertEqual(payload["metadata"]["moveCap"], 300)
        self.assertIn("startedAtEpoch", payload)
        self.assertIn("updatedAtEpoch", payload)
        self.assertIn("elapsedWallTimeSeconds", payload)

    def test_evaluation_request_accepts_time_budget_and_move_cap(self) -> None:
        payload = EvaluationStartRequest(
            games=1,
            variant="british",
            moveCap=450,
            maxDurationSeconds=120,
            white={"type": "minimax", "depth": 2},
            black={"type": "mcts", "iterations": 10},
        )

        self.assertEqual(payload.moveCap, 450)
        self.assertEqual(payload.maxDurationSeconds, 120)

    def test_evaluation_time_budget_sets_stop_reason(self) -> None:
        session = session_module.GameSession()
        state = session_module.EvaluationState(
            evaluation_id="eval-time-budget",
            config={
                "variant": "british",
                "drawPolicy": "half",
                "moveCap": 300,
                "maxDurationSeconds": 1,
                "white": {"type": "minimax", "depth": 1},
                "black": {"type": "mcts", "iterations": 1},
            },
            total_games=10,
            results=[],
            running=True,
            stop_event=threading.Event(),
            deadline_at_epoch=time.time() - 1,
        )

        session._run_evaluation(state)
        payload = session._evaluation_status_payload(state)

        self.assertFalse(payload["running"])
        self.assertEqual(payload["stopReason"], "time_budget")

    def test_evaluation_export_omits_reset_configs_after_run(self) -> None:
        session = session_module.GameSession()
        state = self._make_evaluation_state("half")
        with session._evaluation_lock:
            session._evaluations[state.evaluation_id] = state
        try:
            content_type, csv_text = session.get_evaluation_results(state.evaluation_id, "csv")
        finally:
            with session._evaluation_lock:
                session._evaluations.pop(state.evaluation_id, None)

        self.assertEqual(content_type, "text/csv")
        self.assertNotIn("resetConfigsAfterRun", csv_text)
        self.assertIn("drawPolicy", csv_text)
        self.assertIn("maxDurationSeconds", csv_text)
        self.assertIn("stopReason", csv_text)

    def test_reset_cancels_real_parallel_minimax(self) -> None:
        session = session_module.GameSession()

        payload = AIMoveRequest(
            algorithm="minimax",
            color="white",
            depth=12,
            parallel=True,
            workers=4,
            persist=False,
            commitImmediately=False,
        )

        outcome: list[BaseException] = []

        def worker() -> None:
            try:
                session.run_ai_move(payload)
            except BaseException as exc:  # noqa: BLE001
                outcome.append(exc)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        time.sleep(0.05)

        t0 = time.perf_counter()
        session.reset()
        dt = time.perf_counter() - t0
        self.assertLess(dt, 0.5, "reset took too long while parallel minimax was thinking.")

        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive(), "run_ai_move did not stop after reset.")
        self.assertFalse(outcome, f"run_ai_move raised unexpected exception: {outcome!r}")


if __name__ == "__main__":
    unittest.main()
