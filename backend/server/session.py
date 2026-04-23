from __future__ import annotations

from dataclasses import dataclass, field
import os
import json
import csv
import io
import time
import uuid
import threading
import random
from copy import deepcopy
from threading import Lock, RLock
from typing import Any, Callable, Iterable, Optional

from ai.agents import create_minimax_controller, create_mcts_controller
from ai.cancel import CancelledError
from core.board import Board, UndoRecord
from core.game import Game, MoveRecord
from core.move import Move
from core.pieces import Color, King, Man, Piece, reserve_piece_ids_through
from core.player import PlayerController

from .schemas import (
    AIMoveRequest,
    ConfigRequest,
    MoveRequest,
    PerformAIMoveRequest,
    ResetRequest,
    VariantRequest,
    EvaluationStartRequest,
    EvaluationStopRequest,
)
from .serializers import serialize_game, serialize_move

VARIANT_TO_SIZE = {"british": 8, "international": 10}


def _default_player_settings() -> dict[str, Any]:
    return {
        "type": "human",
        "depth": 4,
        "alphaBeta": True,
        "transposition": True,
        "moveOrdering": True,
        "killerMoves": True,
        "iterativeDeepening": False,
        "quiescence": True,
        "maxQuiescenceDepth": 6,
        "aspiration": False,
        "aspirationWindow": 50.0,
        "historyHeuristic": False,
        "butterflyHeuristic": False,
        "nullMove": False,
        "nullMoveReduction": 2,
        "lmr": False,
        "lmrMinDepth": 3,
        "lmrMinMoves": 4,
        "lmrReduction": 1,
        "deterministicOrdering": True,
        "endgameTablebase": False,
        "endgameMaxPieces": 6,
        "endgameMaxPlies": 40,
        "timeLimitMs": 1000,
        "parallel": False,
        "workers": 4,
        "iterations": 500,
        "rolloutDepth": 80,
        "explorationConstant": 1.4,
        "randomSeed": None,
        "mctsParallel": False,
        "mctsWorkers": 4,
        "rolloutPolicy": "random",
        "guidanceDepth": 2,
        "rolloutCutoffDepth": 40,
        "leafEvaluation": "random_terminal",
        "mctsTransposition": False,
        "mctsTranspositionMaxEntries": 200_000,
        "progressiveWidening": False,
        "pwK": 1.5,
        "pwAlpha": 0.5,
        "progressiveBias": False,
        "pbWeight": 0.4,
    }


def _color_from_label(label: str) -> Color:
    try:
        return Color[label.upper()]
    except KeyError as exc:
        raise ValueError(f"Unsupported color '{label}'.") from exc


@dataclass
class PendingAIMove:
	color: Color
	move: Move
	start: tuple[int, int]


@dataclass
class EvaluationResult:
    index: int
    winner: Optional[str]
    move_count: int
    duration_seconds: float
    avg_move_time_white: float
    avg_move_time_black: float
    starting_color: str


@dataclass
class EvaluationState:
    evaluation_id: str
    config: dict[str, Any]
    total_games: int
    results: list[EvaluationResult]
    running: bool
    stop_event: threading.Event
    thread: Optional[threading.Thread] = None
    started_at_epoch: float = field(default_factory=time.time)
    updated_at_epoch: float = field(default_factory=time.time)
    deadline_at_epoch: Optional[float] = None
    stop_reason: Optional[str] = None
    completed_at_epoch: Optional[float] = None
    error_message: Optional[str] = None
    on_finished: Optional[Callable[[], None]] = None


class GameSession:
    """Thread-safe orchestrator around a single Game instance."""

    def __init__(self, on_change: Optional[Callable[[dict[str, Any]], None]] = None) -> None:
        self.lock = RLock()
        self.variant = "british"
        self.game = Game(board_size=VARIANT_TO_SIZE[self.variant])
        self._state_version = 0
        self._ai_job_lock = Lock()
        self._ai_job_seq = 0
        self._ai_active_job_id = 0
        self._ai_cancel_event: Optional[threading.Event] = None
        self._on_change = on_change
        self.player_settings: dict[Color, dict[str, Any]] = {
            Color.WHITE: _default_player_settings(),
            Color.BLACK: _default_player_settings(),
        }
        self._apply_player_controllers()
        self.pending_ai_moves: dict[Color, Optional[PendingAIMove]] = {
            Color.WHITE: None,
            Color.BLACK: None,
        }
        self._evaluation_lock = Lock()
        self._evaluations: dict[str, EvaluationState] = {}

    # public API ---------------------------------------------------------

    def cancel_ai(self) -> None:
        """Signal any in-flight AI computation to stop ASAP."""
        with self._ai_job_lock:
            if self._ai_cancel_event is not None:
                self._ai_cancel_event.set()

    def _start_ai_job(self) -> tuple[int, threading.Event]:
        with self._ai_job_lock:
            if self._ai_cancel_event is not None:
                self._ai_cancel_event.set()
            self._ai_job_seq += 1
            self._ai_active_job_id = self._ai_job_seq
            self._ai_cancel_event = threading.Event()
            return self._ai_active_job_id, self._ai_cancel_event

    def serialize(self) -> dict[str, Any]:
        with self.lock:
            return self._serialize_locked()

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return self._snapshot_locked()

    def resume_pending_evaluations(
        self,
        *,
        acquire_slot: Optional[Callable[[], bool]] = None,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> None:
        pending: list[EvaluationState] = []
        with self._evaluation_lock:
            for state in self._evaluations.values():
                if state.running and (state.thread is None or not state.thread.is_alive()):
                    state.stop_event = threading.Event()
                    pending.append(state)

        changed = False
        for state in pending:
            if acquire_slot is not None and not acquire_slot():
                with self._evaluation_lock:
                    state.running = False
                    state.stop_reason = "global_limit_on_resume"
                    state.updated_at_epoch = time.time()
                    state.completed_at_epoch = time.time()
                changed = True
                continue
            with self._evaluation_lock:
                state.on_finished = on_finished
            self._launch_evaluation_thread(state)
        if changed:
            self._persist_evaluations()

    @classmethod
    def from_snapshot(
        cls,
        snapshot: dict[str, Any],
        *,
        on_change: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> "GameSession":
        session = cls(on_change=on_change)
        with session.lock:
            session.variant = snapshot.get("variant", "british")
            session._state_version = int(snapshot.get("stateVersion", 0))
            session.player_settings = session._restore_player_settings(snapshot.get("playerSettings"))
            session.game = session._restore_game(snapshot.get("game"))
            session.pending_ai_moves = session._restore_pending_moves(snapshot.get("pendingAiMoves"))
            session._evaluations = session._restore_evaluations(snapshot.get("evaluations"))
            session._apply_player_controllers()
        return session

    def reset(self, payload: Optional[ResetRequest] = None) -> dict[str, Any]:
        self.cancel_ai()
        with self.lock:
            if payload and payload.variant:
                self.variant = payload.variant
            self.game.reset(board_size=VARIANT_TO_SIZE[self.variant])
            self._state_version += 1
            self._clear_pending_ai_moves()
            self._apply_player_controllers()
            self._emit_change_locked()
            return self._serialize_locked()

    def set_variant(self, payload: VariantRequest) -> dict[str, Any]:
        self.cancel_ai()
        with self.lock:
            self.variant = payload.variant
            self.game.reset(board_size=VARIANT_TO_SIZE[self.variant])
            self._state_version += 1
            self._clear_pending_ai_moves()
            self._apply_player_controllers()
            self._emit_change_locked()
            return self._serialize_locked()

    def configure_players(self, payload: ConfigRequest) -> dict[str, Any]:
        self.cancel_ai()
        with self.lock:
            config = payload.model_dump(exclude_unset=True)
            if not config:
                return self._serialize_locked()

            for color_label, overrides in config.items():
                color = _color_from_label(color_label)
                merged = deepcopy(self.player_settings[color])
                for key, value in overrides.items():
                    if value is not None:
                        merged[key] = value
                controller = self._controller_from_settings(color, merged)
                self.player_settings[color] = merged
                self.game.setPlayer(color, controller)

            self._state_version += 1
            self._clear_pending_ai_moves()
            self._emit_change_locked()
            return self._serialize_locked()

    def get_valid_moves(self, row: int, col: int) -> dict[str, Any]:
        with self.lock:
            piece = self._require_piece(row, col)
            if piece.color != self.game.current_player:
                raise ValueError("It is not this piece's turn.")
            moves = self.game.getValidMoves().get(piece, [])
            return {
                "piece": {"row": row, "col": col},
                "moves": [serialize_move(move) for move in moves],
            }

    def make_move(self, payload: MoveRequest) -> dict[str, Any]:
        self.cancel_ai()
        with self.lock:
            piece = self._require_piece(payload.start.row, payload.start.col)
            if piece.color != self.game.current_player:
                raise ValueError("Selected piece cannot move now.")
            steps = tuple((node.row, node.col) for node in payload.steps)
            move = self._locate_matching_move(piece, steps)
            if move is None:
                raise ValueError("Requested move path is invalid for this piece.")
            if not self.game.makeMove(piece, move):
                raise RuntimeError("Move execution failed.")
            self._state_version += 1
            self._clear_pending_ai_moves()
            self._emit_change_locked()
            return self._serialize_locked()

    def run_ai_move(self, payload: AIMoveRequest) -> dict[str, Any]:
        job_id, cancel_event = self._start_ai_job()

        with self.lock:
            color = self.game.current_player if payload.color is None else _color_from_label(payload.color)
            if color != self.game.current_player:
                raise ValueError("AI move requested for color that is not on turn.")
            if self.game.winner is not None:
                return self._serialize_locked()
            winner = self.game.board.is_game_over()
            if winner is not None:
                self.game.winner = winner
                self._state_version += 1
                self._clear_pending_ai_moves()
                self._emit_change_locked()
                return self._serialize_locked()

            overrides = deepcopy(self.player_settings[color])
            overrides["type"] = payload.algorithm
            if payload.depth is not None:
                overrides["depth"] = payload.depth
            if payload.alphaBeta is not None:
                overrides["alphaBeta"] = payload.alphaBeta
            if payload.transposition is not None:
                overrides["transposition"] = payload.transposition
            if payload.moveOrdering is not None:
                overrides["moveOrdering"] = payload.moveOrdering
            if payload.killerMoves is not None:
                overrides["killerMoves"] = payload.killerMoves
            if payload.iterativeDeepening is not None:
                overrides["iterativeDeepening"] = payload.iterativeDeepening
            if payload.quiescence is not None:
                overrides["quiescence"] = payload.quiescence
            if payload.maxQuiescenceDepth is not None:
                overrides["maxQuiescenceDepth"] = payload.maxQuiescenceDepth
            if payload.aspiration is not None:
                overrides["aspiration"] = payload.aspiration
            if payload.aspirationWindow is not None:
                overrides["aspirationWindow"] = payload.aspirationWindow
            if payload.historyHeuristic is not None:
                overrides["historyHeuristic"] = payload.historyHeuristic
            if payload.butterflyHeuristic is not None:
                overrides["butterflyHeuristic"] = payload.butterflyHeuristic
            if payload.nullMove is not None:
                overrides["nullMove"] = payload.nullMove
            if payload.nullMoveReduction is not None:
                overrides["nullMoveReduction"] = payload.nullMoveReduction
            if payload.lmr is not None:
                overrides["lmr"] = payload.lmr
            if payload.lmrMinDepth is not None:
                overrides["lmrMinDepth"] = payload.lmrMinDepth
            if payload.lmrMinMoves is not None:
                overrides["lmrMinMoves"] = payload.lmrMinMoves
            if payload.lmrReduction is not None:
                overrides["lmrReduction"] = payload.lmrReduction
            if payload.deterministicOrdering is not None:
                overrides["deterministicOrdering"] = payload.deterministicOrdering
            if payload.endgameTablebase is not None:
                overrides["endgameTablebase"] = payload.endgameTablebase
            if payload.endgameMaxPieces is not None:
                overrides["endgameMaxPieces"] = payload.endgameMaxPieces
            if payload.endgameMaxPlies is not None:
                overrides["endgameMaxPlies"] = payload.endgameMaxPlies
            if payload.timeLimitMs is not None:
                overrides["timeLimitMs"] = payload.timeLimitMs
            if payload.parallel is not None:
                overrides["parallel"] = payload.parallel
            if payload.workers is not None:
                overrides["workers"] = payload.workers
            if payload.iterations is not None:
                overrides["iterations"] = payload.iterations
            if payload.rolloutDepth is not None:
                overrides["rolloutDepth"] = payload.rolloutDepth
            if payload.explorationConstant is not None:
                overrides["explorationConstant"] = payload.explorationConstant
            if payload.randomSeed is not None:
                overrides["randomSeed"] = payload.randomSeed
            if payload.mctsParallel is not None:
                overrides["mctsParallel"] = payload.mctsParallel
            if payload.mctsWorkers is not None:
                overrides["mctsWorkers"] = payload.mctsWorkers
            if payload.rolloutPolicy is not None:
                overrides["rolloutPolicy"] = payload.rolloutPolicy
            if payload.guidanceDepth is not None:
                overrides["guidanceDepth"] = payload.guidanceDepth
            if payload.rolloutCutoffDepth is not None:
                overrides["rolloutCutoffDepth"] = payload.rolloutCutoffDepth
            if payload.leafEvaluation is not None:
                overrides["leafEvaluation"] = payload.leafEvaluation
            if payload.mctsTransposition is not None:
                overrides["mctsTransposition"] = payload.mctsTransposition
            if payload.mctsTranspositionMaxEntries is not None:
                overrides["mctsTranspositionMaxEntries"] = payload.mctsTranspositionMaxEntries
            if payload.progressiveWidening is not None:
                overrides["progressiveWidening"] = payload.progressiveWidening
            if payload.pwK is not None:
                overrides["pwK"] = payload.pwK
            if payload.pwAlpha is not None:
                overrides["pwAlpha"] = payload.pwAlpha
            if payload.progressiveBias is not None:
                overrides["progressiveBias"] = payload.progressiveBias
            if payload.pbWeight is not None:
                overrides["pbWeight"] = payload.pbWeight

            controller = self._controller_from_settings(color, overrides)
            self.game.setPlayer(color, controller)
            if payload.persist:
                self.player_settings[color] = overrides

            commit_now = payload.commitImmediately
            if not commit_now and self.pending_ai_moves[color]:
                raise RuntimeError("AI move already pending for this color.")

            start_version = self._state_version
            snapshot = Game(board_size=self.game.board.boardSize)
            snapshot.board = self.game.board.copy()
            snapshot.current_player = self.game.current_player
            snapshot.winner = self.game.winner
            snapshot.players = self.game.players

        try:
            decision = controller.select_move(snapshot, cancel_event=cancel_event)
        except CancelledError:
            with self.lock:
                return self._serialize_locked()

        if decision is None:
            raise RuntimeError("AI controller could not choose a move.")
        _, move = decision

        with self.lock:
            if job_id != self._ai_active_job_id or cancel_event.is_set() or start_version != self._state_version:
                return self._serialize_locked()
            if color != self.game.current_player:
                return self._serialize_locked()

            if commit_now:
                self._clear_pending_ai_move(color)
                piece = self._require_piece(*move.start)
                if piece.color != color:
                    return self._serialize_locked()
                if not self.game.makeMove(piece, move):
                    raise RuntimeError("Move execution failed.")
                self._state_version += 1
            else:
                self.pending_ai_moves[color] = PendingAIMove(color=color, move=move, start=move.start)
            self._emit_change_locked()
            return self._serialize_locked()

    def perform_ai_move(self, payload: PerformAIMoveRequest) -> dict[str, Any]:
        with self.lock:
            color = _color_from_label(payload.color)
            if color != self.game.current_player:
                self._clear_pending_ai_move(color)
                raise ValueError("Cannot perform AI move when it is not this color's turn.")
            pending = self.pending_ai_moves.get(color)
            if not pending:
                raise ValueError("No pending AI move for this color.")
            try:
                piece = self._require_piece(*pending.start)
            except ValueError as exc:
                self._clear_pending_ai_move(color)
                raise RuntimeError("Pending move references a missing piece.") from exc
            if piece.color != color:
                self._clear_pending_ai_move(color)
                raise RuntimeError("Pending move references the wrong piece.")
            if not self.game.makeMove(piece, pending.move):
                self._clear_pending_ai_move(color)
                raise RuntimeError("Move execution failed.")
            self._clear_pending_ai_move(color)
            self._state_version += 1
            self._emit_change_locked()
            return self._serialize_locked()

    def undo_move(self) -> dict[str, Any]:
        self.cancel_ai()
        with self.lock:
            if not self.game.move_history:
                raise ValueError("No moves to undo.")
            self.game.undoMove()
            self._state_version += 1
            self._clear_pending_ai_moves()
            self._emit_change_locked()
            return self._serialize_locked()

    def start_evaluation(
        self,
        payload: EvaluationStartRequest,
        *,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> dict[str, Any]:
        config = payload.model_dump()
        deadline_at_epoch = None
        if payload.maxDurationSeconds is not None:
            deadline_at_epoch = time.time() + payload.maxDurationSeconds
        evaluation_id = str(uuid.uuid4())
        state = EvaluationState(
            evaluation_id=evaluation_id,
            config=config,
            total_games=payload.games,
            results=[],
            running=True,
            stop_event=threading.Event(),
            deadline_at_epoch=deadline_at_epoch,
            on_finished=on_finished,
        )

        with self._evaluation_lock:
            if any(existing.running for existing in self._evaluations.values()):
                raise ValueError("Another evaluation is already running for this session.")
            self._evaluations[evaluation_id] = state
        self._persist_evaluations()

        self._launch_evaluation_thread(state)
        return self._evaluation_status_payload(state)

    def stop_evaluation(self, payload: EvaluationStopRequest) -> dict[str, Any]:
        with self._evaluation_lock:
            state = self._evaluations.get(payload.evaluationId)
        if not state:
            raise ValueError("Unknown evaluation id.")
        state.stop_event.set()
        with self._evaluation_lock:
            if state.stop_reason is None:
                state.stop_reason = "stopped_by_user"
            state.updated_at_epoch = time.time()
        self._persist_evaluations()
        return self._evaluation_status_payload(state)

    def get_evaluation_status(self, evaluation_id: str) -> dict[str, Any]:
        with self._evaluation_lock:
            state = self._evaluations.get(evaluation_id)
        if not state:
            raise ValueError("Unknown evaluation id.")
        return self._evaluation_status_payload(state)

    def has_running_evaluation(self) -> bool:
        with self._evaluation_lock:
            return any(state.running for state in self._evaluations.values())

    def get_evaluation_results(self, evaluation_id: str, format: str) -> tuple[str, Any]:
        with self._evaluation_lock:
            state = self._evaluations.get(evaluation_id)
        if not state:
            raise ValueError("Unknown evaluation id.")
        if format not in {"csv", "json"}:
            raise ValueError("Unsupported format.")

        payload = self._evaluation_status_payload(state)
        with self._evaluation_lock:
            results = list(state.results)
        if format == "json":
            return "application/json", payload

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["meta", "variant", state.config.get("variant")])
        writer.writerow(["meta", "games", state.total_games])
        writer.writerow(["meta", "moveCap", state.config.get("moveCap")])
        writer.writerow(["meta", "startPolicy", state.config.get("startPolicy")])
        writer.writerow(["meta", "randomSeed", state.config.get("randomSeed")])
        writer.writerow(["meta", "randomizeOpening", state.config.get("randomizeOpening")])
        writer.writerow(["meta", "randomizePlies", state.config.get("randomizePlies")])
        writer.writerow(["meta", "experimentName", state.config.get("experimentName")])
        writer.writerow(["meta", "notes", state.config.get("notes")])
        writer.writerow(["meta", "drawPolicy", state.config.get("drawPolicy")])
        writer.writerow(["meta", "maxDurationSeconds", state.config.get("maxDurationSeconds")])
        writer.writerow(["meta", "startedAtEpoch", payload.get("startedAtEpoch")])
        writer.writerow(["meta", "updatedAtEpoch", payload.get("updatedAtEpoch")])
        writer.writerow(["meta", "completedAtEpoch", payload.get("completedAtEpoch")])
        writer.writerow(["meta", "deadlineAtEpoch", payload.get("deadlineAtEpoch")])
        writer.writerow(["meta", "elapsedWallTimeSeconds", payload.get("elapsedWallTimeSeconds")])
        writer.writerow(["meta", "stopReason", payload.get("stopReason")])
        writer.writerow(["meta", "error", payload.get("error")])
        writer.writerow(["meta", "whiteConfig", json.dumps(state.config.get("white"), ensure_ascii=False)])
        writer.writerow(["meta", "blackConfig", json.dumps(state.config.get("black"), ensure_ascii=False)])
        writer.writerow([])
        writer.writerow(["summary", "whiteWins", payload["score"].get("whiteWins")])
        writer.writerow(["summary", "blackWins", payload["score"].get("blackWins")])
        writer.writerow(["summary", "draws", payload["score"].get("draws")])
        writer.writerow(["summary", "avgMoves", payload["summary"].get("avgMoves")])
        writer.writerow(["summary", "avgDuration", payload["summary"].get("avgDuration")])
        writer.writerow(["summary", "avgMoveTimeWhite", payload["summary"].get("avgMoveTimeWhite")])
        writer.writerow(["summary", "avgMoveTimeBlack", payload["summary"].get("avgMoveTimeBlack")])
        writer.writerow(["summary", "winRateWhite", payload["summary"].get("winRateWhite")])
        writer.writerow(["summary", "winRateBlack", payload["summary"].get("winRateBlack")])
        writer.writerow([])
        writer.writerow([
            "index",
            "winner",
            "move_count",
            "duration_seconds",
            "avg_move_time_white",
            "avg_move_time_black",
            "starting_color",
        ])
        for result in results:
            writer.writerow([
                result.index,
                result.winner or "draw",
                result.move_count,
                f"{result.duration_seconds:.4f}",
                f"{result.avg_move_time_white:.4f}",
                f"{result.avg_move_time_black:.4f}",
                result.starting_color,
            ])
        return "text/csv", output.getvalue()

    # helpers ------------------------------------------------------------

    def _emit_change_locked(self) -> None:
        if self._on_change is not None:
            self._on_change(self._snapshot_locked())

    def _persist_evaluations(self) -> None:
        with self.lock:
            self._emit_change_locked()

    def _launch_evaluation_thread(self, state: EvaluationState) -> None:
        def runner() -> None:
            try:
                self._run_evaluation(state)
            except BaseException as exc:  # noqa: BLE001
                with self._evaluation_lock:
                    state.running = False
                    state.thread = None
                    state.updated_at_epoch = time.time()
                    state.completed_at_epoch = time.time()
                    state.stop_reason = "error"
                    state.error_message = str(exc)
                self._persist_evaluations()
            finally:
                self._release_evaluation_slot(state)

        thread = threading.Thread(
            target=runner,
            daemon=True,
        )
        with self._evaluation_lock:
            state.thread = thread
        thread.start()

    def _release_evaluation_slot(self, state: EvaluationState) -> None:
        callback: Optional[Callable[[], None]]
        with self._evaluation_lock:
            callback = state.on_finished
            state.on_finished = None
        if callback is not None:
            callback()

    def _serialize_locked(self) -> dict[str, Any]:
        payload = serialize_game(self.game, self.variant, self.player_settings)
        payload["pendingAiMoves"] = {
            "white": self._pending_move_payload(Color.WHITE),
            "black": self._pending_move_payload(Color.BLACK),
        }
        return payload

    def _snapshot_locked(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "stateVersion": self._state_version,
            "playerSettings": {
                "white": deepcopy(self.player_settings[Color.WHITE]),
                "black": deepcopy(self.player_settings[Color.BLACK]),
            },
            "pendingAiMoves": {
                "white": self._snapshot_pending_move(self.pending_ai_moves.get(Color.WHITE)),
                "black": self._snapshot_pending_move(self.pending_ai_moves.get(Color.BLACK)),
            },
            "game": self._snapshot_game_locked(),
            "evaluations": self._snapshot_evaluations_locked(),
        }

    def _snapshot_game_locked(self) -> dict[str, Any]:
        return {
            "board": self.game.board.to_state(),
            "currentPlayer": self.game.current_player.value,
            "winner": self.game.winner.value if self.game.winner else None,
            "moveHistory": [self._snapshot_move_record(record) for record in self.game.move_history],
        }

    def _snapshot_evaluations_locked(self) -> dict[str, Any]:
        with self._evaluation_lock:
            return {
                evaluation_id: {
                    "config": deepcopy(state.config),
                    "totalGames": state.total_games,
                    "results": [self._snapshot_evaluation_result(result) for result in state.results],
                    "running": state.running,
                    "startedAtEpoch": state.started_at_epoch,
                    "updatedAtEpoch": state.updated_at_epoch,
                    "deadlineAtEpoch": state.deadline_at_epoch,
                    "stopReason": state.stop_reason,
                    "completedAtEpoch": state.completed_at_epoch,
                    "errorMessage": state.error_message,
                }
                for evaluation_id, state in self._evaluations.items()
            }

    def _pending_move_payload(self, color: Color) -> Optional[dict[str, Any]]:
        pending = self.pending_ai_moves.get(color)
        if not pending:
            return None
        return {
            "color": pending.color.value,
            "piece": {"row": pending.start[0], "col": pending.start[1]},
            "move": serialize_move(pending.move),
        }

    def _snapshot_pending_move(self, pending: Optional[PendingAIMove]) -> Optional[dict[str, Any]]:
        if pending is None:
            return None
        return {
            "color": pending.color.value,
            "start": list(pending.start),
            "move": self._snapshot_move(pending.move),
        }

    def _snapshot_move_record(self, record: MoveRecord) -> dict[str, Any]:
        return {
            "pieceBefore": self._snapshot_piece(record.piece_before),
            "pieceAfter": self._snapshot_piece(record.piece_after),
            "move": self._snapshot_move(record.move),
            "captured": [self._snapshot_piece(piece) for piece in record.captured],
            "undo": self._snapshot_undo(record.undo),
        }

    def _snapshot_undo(self, undo: Optional[UndoRecord]) -> Optional[dict[str, Any]]:
        if undo is None:
            return None
        return {
            "prevTurn": undo.prev_turn.value,
            "prevHash": undo.prev_hash,
            "pieceBefore": self._snapshot_piece(undo.piece_before),
            "pieceAfter": self._snapshot_piece(undo.piece_after),
            "start": list(undo.start),
            "end": list(undo.end),
            "captured": [self._snapshot_piece(piece) for piece in undo.captured],
            "capturedPositions": [list(position) for position in undo.captured_positions],
        }

    def _snapshot_piece(self, piece: Piece) -> dict[str, Any]:
        return {
            "color": piece.color.value,
            "row": piece.row,
            "col": piece.col,
            "isKing": piece.is_king,
            "id": piece.id,
        }

    def _snapshot_move(self, move: Move) -> dict[str, Any]:
        return {
            "start": list(move.start),
            "steps": [list(step) for step in move.steps],
            "captures": [list(capture) for capture in move.captures],
        }

    def _snapshot_evaluation_result(self, result: EvaluationResult) -> dict[str, Any]:
        return {
            "index": result.index,
            "winner": result.winner,
            "moveCount": result.move_count,
            "durationSeconds": result.duration_seconds,
            "avgMoveTimeWhite": result.avg_move_time_white,
            "avgMoveTimeBlack": result.avg_move_time_black,
            "startingColor": result.starting_color,
        }

    def _restore_player_settings(self, snapshot: Optional[dict[str, Any]]) -> dict[Color, dict[str, Any]]:
        white = _default_player_settings()
        black = _default_player_settings()
        if snapshot and snapshot.get("white"):
            white.update(deepcopy(snapshot["white"]))
        if snapshot and snapshot.get("black"):
            black.update(deepcopy(snapshot["black"]))
        return {
            Color.WHITE: white,
            Color.BLACK: black,
        }

    def _restore_game(self, snapshot: Optional[dict[str, Any]]) -> Game:
        board_state = snapshot.get("board") if snapshot else None
        board_size = int(board_state[0]) if board_state else VARIANT_TO_SIZE.get(self.variant, 8)
        game = Game(board_size=board_size)
        if not board_state:
            return game

        board = Board.from_state(board_state)
        max_piece_id = max((piece.id for piece in board.getAllPieces()), default=-1)
        reserve_piece_ids_through(max_piece_id)

        game.board = board
        current_player = snapshot.get("currentPlayer") if snapshot else None
        game.current_player = _color_from_label(current_player) if current_player else board.turn
        winner = snapshot.get("winner") if snapshot else None
        game.winner = _color_from_label(winner) if winner else None
        move_history = snapshot.get("moveHistory") if snapshot else []
        game.move_history = [self._restore_move_record(record) for record in move_history]
        return game

    def _restore_pending_moves(
        self,
        snapshot: Optional[dict[str, Any]],
    ) -> dict[Color, Optional[PendingAIMove]]:
        return {
            Color.WHITE: self._restore_pending_move(snapshot.get("white") if snapshot else None),
            Color.BLACK: self._restore_pending_move(snapshot.get("black") if snapshot else None),
        }

    def _restore_pending_move(self, snapshot: Optional[dict[str, Any]]) -> Optional[PendingAIMove]:
        if not snapshot:
            return None
        color = _color_from_label(snapshot["color"])
        move = self._restore_move(snapshot["move"])
        start = tuple(snapshot["start"])
        return PendingAIMove(color=color, move=move, start=start)

    def _restore_move_record(self, snapshot: dict[str, Any]) -> MoveRecord:
        return MoveRecord(
            piece_before=self._restore_piece(snapshot["pieceBefore"]),
            piece_after=self._restore_piece(snapshot["pieceAfter"]),
            move=self._restore_move(snapshot["move"]),
            captured=[self._restore_piece(piece) for piece in snapshot.get("captured", [])],
            undo=self._restore_undo(snapshot.get("undo")),
        )

    def _restore_undo(self, snapshot: Optional[dict[str, Any]]) -> Optional[UndoRecord]:
        if not snapshot:
            return None
        return UndoRecord(
            prev_turn=_color_from_label(snapshot["prevTurn"]),
            prev_hash=int(snapshot["prevHash"]),
            piece_before=self._restore_piece(snapshot["pieceBefore"]),
            piece_after=self._restore_piece(snapshot["pieceAfter"]),
            start=tuple(snapshot["start"]),
            end=tuple(snapshot["end"]),
            captured=tuple(self._restore_piece(piece) for piece in snapshot.get("captured", [])),
            captured_positions=tuple(tuple(position) for position in snapshot.get("capturedPositions", [])),
        )

    def _restore_piece(self, snapshot: dict[str, Any]) -> Piece:
        color = _color_from_label(snapshot["color"])
        row = int(snapshot["row"])
        col = int(snapshot["col"])
        identifier = int(snapshot["id"])
        reserve_piece_ids_through(identifier)
        if snapshot.get("isKing"):
            return King(color, row, col, identifier=identifier)
        return Man(color, row, col, identifier=identifier)

    def _restore_move(self, snapshot: dict[str, Any]) -> Move:
        return Move(
            start=tuple(snapshot["start"]),
            steps=tuple(tuple(step) for step in snapshot.get("steps", [])),
            captures=tuple(tuple(capture) for capture in snapshot.get("captures", [])),
        )

    def _restore_evaluations(self, snapshot: Optional[dict[str, Any]]) -> dict[str, EvaluationState]:
        restored: dict[str, EvaluationState] = {}
        if not snapshot:
            return restored
        for evaluation_id, payload in snapshot.items():
            restored[evaluation_id] = EvaluationState(
                evaluation_id=evaluation_id,
                config=deepcopy(payload.get("config", {})),
                total_games=int(payload.get("totalGames", 0)),
                results=[
                    EvaluationResult(
                        index=int(result["index"]),
                        winner=result.get("winner"),
                        move_count=int(result["moveCount"]),
                        duration_seconds=float(result["durationSeconds"]),
                        avg_move_time_white=float(result["avgMoveTimeWhite"]),
                        avg_move_time_black=float(result["avgMoveTimeBlack"]),
                        starting_color=result["startingColor"],
                    )
                    for result in payload.get("results", [])
                ],
                running=bool(payload.get("running")),
                stop_event=threading.Event(),
                started_at_epoch=float(payload.get("startedAtEpoch") or time.time()),
                updated_at_epoch=float(payload.get("updatedAtEpoch") or payload.get("startedAtEpoch") or time.time()),
                deadline_at_epoch=(
                    float(payload["deadlineAtEpoch"])
                    if payload.get("deadlineAtEpoch") is not None
                    else None
                ),
                stop_reason=payload.get("stopReason"),
                completed_at_epoch=(
                    float(payload["completedAtEpoch"])
                    if payload.get("completedAtEpoch") is not None
                    else None
                ),
                error_message=payload.get("errorMessage"),
            )
        return restored

    def _clear_pending_ai_moves(self, color: Optional[Color] = None) -> None:
        if color is None:
            for clr in (Color.WHITE, Color.BLACK):
                self.pending_ai_moves[clr] = None
        else:
            self.pending_ai_moves[color] = None

    def _clear_pending_ai_move(self, color: Color) -> None:
        self._clear_pending_ai_moves(color)

    def _require_piece(self, row: int, col: int) -> Piece:
        piece = self.game.board.getPiece(row, col)
        if piece is None:
            raise ValueError(f"No piece at row {row}, col {col}.")
        return piece

    def _locate_matching_move(self, piece: Piece, steps: Iterable[tuple[int, int]]) -> Optional[Move]:
        candidate = tuple(steps)
        options = self.game.getValidMoves().get(piece, [])
        for move in options:
            if len(move.steps) != len(candidate):
                continue
            if all(a == b for a, b in zip(move.steps, candidate)):
                return move
        return None

    def _apply_player_controllers(self) -> None:
        for color in (Color.WHITE, Color.BLACK):
            controller = self._controller_from_settings(color, self.player_settings[color])
            self.game.setPlayer(color, controller)

    def _controller_from_settings(self, color: Color, settings: dict[str, Any]) -> PlayerController:
        label = "White" if color == Color.WHITE else "Black"
        player_type = settings.get("type", "human")
        if player_type == "human":
            return PlayerController.human(f"{label} Human")
        if player_type == "minimax":
            depth = int(settings.get("depth") or 4)
            use_parallel = bool(settings.get("parallel"))
            workers = int(settings.get("workers") or 1)
            resolved_workers = self._resolve_parallel_workers(color, use_parallel, workers)
            return create_minimax_controller(
                label,
                depth=depth,
                use_alpha_beta=bool(settings.get("alphaBeta", True)),
                use_transposition=bool(settings.get("transposition", True)),
                use_move_ordering=bool(settings.get("moveOrdering", True)),
                use_killer_moves=bool(settings.get("killerMoves", True)),
                use_quiescence=bool(settings.get("quiescence", True)),
                max_quiescence_depth=int(settings.get("maxQuiescenceDepth") or 6),
                use_aspiration=bool(settings.get("aspiration")),
                aspiration_window=float(settings.get("aspirationWindow") or 50.0),
                use_history_heuristic=bool(settings.get("historyHeuristic")),
                use_butterfly_heuristic=bool(settings.get("butterflyHeuristic")),
                use_null_move=bool(settings.get("nullMove")),
                null_move_reduction=int(settings.get("nullMoveReduction") or 2),
                use_lmr=bool(settings.get("lmr")),
                lmr_min_depth=int(settings.get("lmrMinDepth") or 3),
                lmr_min_moves=int(settings.get("lmrMinMoves") or 4),
                lmr_reduction=int(settings.get("lmrReduction") or 1),
                deterministic_ordering=bool(settings.get("deterministicOrdering", True)),
                use_endgame_tablebase=bool(settings.get("endgameTablebase")),
                endgame_max_pieces=int(settings.get("endgameMaxPieces") or 6),
                endgame_max_plies=int(settings.get("endgameMaxPlies") or 40),
                use_iterative_deepening=bool(settings.get("iterativeDeepening")),
                time_limit_ms=int(settings.get("timeLimitMs") or 1000),
                use_parallel=use_parallel,
                workers=resolved_workers,
            )
        if player_type == "mcts":
            iterations = int(settings.get("iterations") or 500)
            rollout_depth = int(settings.get("rolloutDepth") or 80)
            exploration_constant = float(settings.get("explorationConstant") or 1.4)
            random_seed = settings.get("randomSeed")
            mcts_parallel = bool(settings.get("mctsParallel"))
            mcts_workers = int(settings.get("mctsWorkers") or 1)
            resolved_mcts_workers = self._resolve_parallel_workers(color, mcts_parallel, mcts_workers)
            rollout_policy = settings.get("rolloutPolicy") or "random"
            guidance_depth = int(settings.get("guidanceDepth") or 1)
            rollout_cutoff_depth = settings.get("rolloutCutoffDepth")
            leaf_evaluation = settings.get("leafEvaluation") or "random_terminal"
            return create_mcts_controller(
                label,
                iterations=iterations,
                rollout_depth=rollout_depth,
                exploration_constant=exploration_constant,
                random_seed=random_seed,
                use_parallel=mcts_parallel,
                workers=resolved_mcts_workers,
                rollout_policy=rollout_policy,
                guidance_depth=guidance_depth,
                rollout_cutoff_depth=rollout_cutoff_depth,
                leaf_evaluation=leaf_evaluation,
                use_transposition=bool(settings.get("mctsTransposition")),
                transposition_max_entries=int(settings.get("mctsTranspositionMaxEntries") or 200_000),
                progressive_widening=bool(settings.get("progressiveWidening")),
                pw_k=float(settings.get("pwK") or 1.5),
                pw_alpha=float(settings.get("pwAlpha") or 0.5),
                progressive_bias=bool(settings.get("progressiveBias")),
                pb_weight=float(settings.get("pbWeight") or 0.0),
            )
        raise ValueError(f"Player type '{player_type}' not implemented yet.")

    def _run_evaluation(self, state: EvaluationState) -> None:
        config = state.config
        variant = config["variant"]
        start_policy = config.get("startPolicy", "alternate")
        random_seed = config.get("randomSeed")
        randomize_opening = bool(config.get("randomizeOpening"))
        randomize_plies = int(config.get("randomizePlies") or 0)
        move_cap = int(config.get("moveCap") or 300)
        total_games = state.total_games

        rng = random.Random(random_seed) if random_seed is not None else random.Random()
        with self._evaluation_lock:
            completed_games = len(state.results)

        for index in range(completed_games + 1, total_games + 1):
            if self._deadline_reached(state):
                self._mark_deadline_stop(state)
            if state.stop_event.is_set():
                break

            game = Game(board_size=VARIANT_TO_SIZE[variant])
            white_settings = config["white"]
            black_settings = config["black"]

            white_controller = self._controller_from_settings(Color.WHITE, white_settings)
            black_controller = self._controller_from_settings(Color.BLACK, black_settings)
            game.setPlayer(Color.WHITE, white_controller)
            game.setPlayer(Color.BLACK, black_controller)

            starting_color = Color.WHITE
            if start_policy == "black" or (start_policy == "alternate" and index % 2 == 0):
                starting_color = Color.BLACK
                game.board.turn = Color.BLACK
                game.board.zobrist_hash = game.board.recompute_hash()
                game.board._moves_cache.clear()
                game.current_player = Color.BLACK

            total_time_white = 0.0
            total_time_black = 0.0
            moves_white = 0
            moves_black = 0
            start_time = time.perf_counter()

            for ply in range(move_cap):
                if self._deadline_reached(state):
                    self._mark_deadline_stop(state)
                if state.stop_event.is_set():
                    break

                winner = game.board.is_game_over()
                if winner is not None:
                    game.winner = winner
                    break

                controller = game.currentController()
                if randomize_opening and rng and ply < randomize_plies:
                    moves_map = game.board.getAllValidMoves(game.current_player)
                    moves = [move for moves in moves_map.values() for move in moves]
                    if not moves:
                        break
                    move = rng.choice(moves)
                    piece = game.board.getPiece(*move.start)
                    if piece is None:
                        break
                    game.makeMove(piece, move)
                    continue

                move_start = time.perf_counter()
                try:
                    decision = controller.select_move(game, cancel_event=state.stop_event)
                except CancelledError:
                    break
                move_end = time.perf_counter()
                if decision is None:
                    break

                piece, move = decision
                mover_color = piece.color
                if not game.makeMove(piece, move):
                    break

                elapsed = move_end - move_start
                if controller.kind.value == "human":
                    continue
                if mover_color == Color.WHITE:
                    total_time_white += elapsed
                    moves_white += 1
                else:
                    total_time_black += elapsed
                    moves_black += 1

            duration = time.perf_counter() - start_time
            winner = game.winner.value if game.winner else None
            avg_white = total_time_white / max(1, moves_white)
            avg_black = total_time_black / max(1, moves_black)

            with self._evaluation_lock:
                state.results.append(
                    EvaluationResult(
                        index=index,
                        winner=winner,
                        move_count=len(game.move_history),
                        duration_seconds=duration,
                        avg_move_time_white=avg_white,
                        avg_move_time_black=avg_black,
                        starting_color=starting_color.value,
                    )
                )
                state.updated_at_epoch = time.time()
            self._persist_evaluations()

        with self._evaluation_lock:
            state.running = False
            state.thread = None
            state.updated_at_epoch = time.time()
            state.completed_at_epoch = time.time()
            if state.stop_reason is None:
                if state.error_message:
                    state.stop_reason = "error"
                elif state.stop_event.is_set():
                    state.stop_reason = "time_budget" if self._deadline_reached(state) else "stopped_by_user"
                else:
                    state.stop_reason = "completed_games"
        self._persist_evaluations()

    def _evaluation_status_payload(self, state: EvaluationState) -> dict[str, Any]:
        with self._evaluation_lock:
            results = list(state.results)
            running = state.running
            deadline_at_epoch = state.deadline_at_epoch
            started_at_epoch = state.started_at_epoch
            updated_at_epoch = state.updated_at_epoch
            completed_at_epoch = state.completed_at_epoch
            stop_reason = state.stop_reason
            error_message = state.error_message
        elapsed_wall_time_seconds = max(0.0, (completed_at_epoch or time.time()) - started_at_epoch)
        white_wins = sum(1 for result in results if result.winner == "white")
        black_wins = sum(1 for result in results if result.winner == "black")
        draws = sum(1 for result in results if result.winner is None)
        total = max(1, len(results))
        avg_moves = sum(result.move_count for result in results) / total
        avg_duration = sum(result.duration_seconds for result in results) / total
        avg_white_time = sum(result.avg_move_time_white for result in results) / total
        avg_black_time = sum(result.avg_move_time_black for result in results) / total
        white_rate, black_rate = self._evaluation_win_rates(white_wins, black_wins, draws, state.config.get("drawPolicy"))

        return {
            "schema_version": "1.0",
            "evaluationId": state.evaluation_id,
            "running": running,
            "completedGames": len(results),
            "totalGames": state.total_games,
            "startedAtEpoch": started_at_epoch,
            "updatedAtEpoch": updated_at_epoch,
            "completedAtEpoch": completed_at_epoch,
            "deadlineAtEpoch": deadline_at_epoch,
            "elapsedWallTimeSeconds": elapsed_wall_time_seconds,
            "stopReason": stop_reason,
            "error": error_message,
            "config": state.config,
            "metadata": {
                "variant": state.config.get("variant"),
                "games": state.total_games,
                "moveCap": state.config.get("moveCap"),
                "maxDurationSeconds": state.config.get("maxDurationSeconds"),
                "startPolicy": state.config.get("startPolicy"),
                "randomSeed": state.config.get("randomSeed"),
                "randomizeOpening": state.config.get("randomizeOpening"),
                "randomizePlies": state.config.get("randomizePlies"),
                "experimentName": state.config.get("experimentName"),
                "notes": state.config.get("notes"),
                "drawPolicy": state.config.get("drawPolicy"),
                "deadlineAtEpoch": deadline_at_epoch,
                "whiteConfig": state.config.get("white"),
                "blackConfig": state.config.get("black"),
            },
            "score": {
                "whiteWins": white_wins,
                "blackWins": black_wins,
                "draws": draws,
            },
            "summary": {
                "avgMoves": avg_moves,
                "avgDuration": avg_duration,
                "avgMoveTimeWhite": avg_white_time,
                "avgMoveTimeBlack": avg_black_time,
                "winRateWhite": white_rate,
                "winRateBlack": black_rate,
            },
            "results": [
                {
                    "index": result.index,
                    "winner": result.winner,
                    "moveCount": result.move_count,
                    "durationSeconds": result.duration_seconds,
                    "avgMoveTimeWhite": result.avg_move_time_white,
                    "avgMoveTimeBlack": result.avg_move_time_black,
                    "startingColor": result.starting_color,
                }
                for result in results
            ],
        }

    def _deadline_reached(self, state: EvaluationState) -> bool:
        deadline = state.deadline_at_epoch
        return deadline is not None and time.time() >= deadline

    def _mark_deadline_stop(self, state: EvaluationState) -> None:
        with self._evaluation_lock:
            if state.stop_reason is None:
                state.stop_reason = "time_budget"
            state.updated_at_epoch = time.time()
        state.stop_event.set()

    def _evaluation_win_rates(
        self,
        white_wins: int,
        black_wins: int,
        draws: int,
        draw_policy: Optional[str],
    ) -> tuple[float, float]:
        policy = draw_policy or "half"
        total_games = white_wins + black_wins + draws
        if total_games <= 0:
            return 0.0, 0.0
        if policy == "ignore":
            decisive_games = white_wins + black_wins
            if decisive_games <= 0:
                return 0.0, 0.0
            return white_wins / decisive_games, black_wins / decisive_games
        if policy == "half":
            return (white_wins + 0.5 * draws) / total_games, (black_wins + 0.5 * draws) / total_games
        return white_wins / total_games, black_wins / total_games

    def _resolve_parallel_workers(self, color: Color, use_parallel: bool, requested: int) -> int:
        if not use_parallel:
            return 1
        cpu_total = os.cpu_count() or 1
        global_max = max(1, cpu_total - 2)
        other_color = Color.BLACK if color == Color.WHITE else Color.WHITE
        other_settings = self.player_settings.get(other_color, {})
        other_parallel = bool(other_settings.get("parallel") or other_settings.get("mctsParallel"))
        share = max(1, global_max // 2) if other_parallel else global_max
        return min(max(1, requested), share)
