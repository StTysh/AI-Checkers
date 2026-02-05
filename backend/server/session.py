from __future__ import annotations

from dataclasses import dataclass
import os
import json
import csv
import io
import time
import uuid
import threading
import random
from copy import deepcopy
from threading import Lock
from typing import Any, Iterable, Optional

from ai.agents import create_minimax_controller, create_mcts_controller
from ai.cancel import CancelledError
from core.game import Game
from core.move import Move
from core.pieces import Color, Piece
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


class GameSession:
    """Thread-safe orchestrator around a single Game instance."""

    def __init__(self) -> None:
        self.lock = Lock()
        self.variant = "british"
        self.game = Game(board_size=VARIANT_TO_SIZE[self.variant])
        self._state_version = 0
        self._ai_job_lock = Lock()
        self._ai_job_seq = 0
        self._ai_active_job_id = 0
        self._ai_cancel_event: Optional[threading.Event] = None
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

    def reset(self, payload: Optional[ResetRequest] = None) -> dict[str, Any]:
        self.cancel_ai()
        with self.lock:
            if payload and payload.variant:
                self.variant = payload.variant
            self.game.reset(board_size=VARIANT_TO_SIZE[self.variant])
            self._state_version += 1
            self._clear_pending_ai_moves()
            self._apply_player_controllers()
            return self._serialize_locked()

    def set_variant(self, payload: VariantRequest) -> dict[str, Any]:
        self.cancel_ai()
        with self.lock:
            self.variant = payload.variant
            self.game.reset(board_size=VARIANT_TO_SIZE[self.variant])
            self._state_version += 1
            self._clear_pending_ai_moves()
            self._apply_player_controllers()
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
            return self._serialize_locked()

    def run_ai_move(self, payload: AIMoveRequest) -> dict[str, Any]:
        job_id, cancel_event = self._start_ai_job()

        with self.lock:
            color = self.game.current_player if payload.color is None else _color_from_label(payload.color)
            if color != self.game.current_player:
                raise ValueError("AI move requested for color that is not on turn.")

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
            return self._serialize_locked()

    def undo_move(self) -> dict[str, Any]:
        self.cancel_ai()
        with self.lock:
            if not self.game.move_history:
                raise ValueError("No moves to undo.")
            self.game.undoMove()
            self._state_version += 1
            self._clear_pending_ai_moves()
            return self._serialize_locked()

    def start_evaluation(self, payload: EvaluationStartRequest) -> dict[str, Any]:
        config = payload.model_dump()
        evaluation_id = str(uuid.uuid4())
        state = EvaluationState(
            evaluation_id=evaluation_id,
            config=config,
            total_games=payload.games,
            results=[],
            running=True,
            stop_event=threading.Event(),
        )

        thread = threading.Thread(
            target=self._run_evaluation,
            args=(state,),
            daemon=True,
        )
        state.thread = thread

        with self._evaluation_lock:
            self._evaluations[evaluation_id] = state

        thread.start()
        return self._evaluation_status_payload(state)

    def stop_evaluation(self, payload: EvaluationStopRequest) -> dict[str, Any]:
        with self._evaluation_lock:
            state = self._evaluations.get(payload.evaluationId)
        if not state:
            raise ValueError("Unknown evaluation id.")
        state.stop_event.set()
        return self._evaluation_status_payload(state)

    def get_evaluation_status(self, evaluation_id: str) -> dict[str, Any]:
        with self._evaluation_lock:
            state = self._evaluations.get(evaluation_id)
        if not state:
            raise ValueError("Unknown evaluation id.")
        return self._evaluation_status_payload(state)

    def get_evaluation_results(self, evaluation_id: str, format: str) -> tuple[str, str]:
        with self._evaluation_lock:
            state = self._evaluations.get(evaluation_id)
        if not state:
            raise ValueError("Unknown evaluation id.")
        if format not in {"csv", "json"}:
            raise ValueError("Unsupported format.")

        payload = self._evaluation_status_payload(state)
        if format == "json":
            return "application/json", payload

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["meta", "variant", state.config.get("variant")])
        writer.writerow(["meta", "games", state.total_games])
        writer.writerow(["meta", "startPolicy", state.config.get("startPolicy")])
        writer.writerow(["meta", "randomSeed", state.config.get("randomSeed")])
        writer.writerow(["meta", "randomizeOpening", state.config.get("randomizeOpening")])
        writer.writerow(["meta", "randomizePlies", state.config.get("randomizePlies")])
        writer.writerow(["meta", "resetConfigsAfterRun", state.config.get("resetConfigsAfterRun")])
        writer.writerow(["meta", "experimentName", state.config.get("experimentName")])
        writer.writerow(["meta", "notes", state.config.get("notes")])
        writer.writerow(["meta", "drawPolicy", state.config.get("drawPolicy")])
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
        for result in state.results:
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

    def _serialize_locked(self) -> dict[str, Any]:
        payload = serialize_game(self.game, self.variant, self.player_settings)
        payload["pendingAiMoves"] = {
            "white": self._pending_move_payload(Color.WHITE),
            "black": self._pending_move_payload(Color.BLACK),
        }
        return payload

    def _pending_move_payload(self, color: Color) -> Optional[dict[str, Any]]:
        pending = self.pending_ai_moves.get(color)
        if not pending:
            return None
        return {
            "color": pending.color.value,
            "piece": {"row": pending.start[0], "col": pending.start[1]},
            "move": serialize_move(pending.move),
        }

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
                workers=mcts_workers,
                rollout_policy=rollout_policy,
                guidance_depth=guidance_depth,
                rollout_cutoff_depth=rollout_cutoff_depth,
                leaf_evaluation=leaf_evaluation,
                use_transposition=bool(settings.get("mctsTransposition")),
                transposition_max_entries=int(settings.get("mctsTranspositionMaxEntries") or 200_000),
                progressive_widening=bool(settings.get("progressiveWidening")),
                pw_k=float(settings.get("pwK") or 1.5),
                pw_alpha=float(settings.get("pwAlpha") or 0.5),
            )
        raise ValueError(f"Player type '{player_type}' not implemented yet.")

    def _run_evaluation(self, state: EvaluationState) -> None:
        config = state.config
        variant = config["variant"]
        start_policy = config.get("startPolicy", "alternate")
        random_seed = config.get("randomSeed")
        randomize_opening = bool(config.get("randomizeOpening"))
        randomize_plies = int(config.get("randomizePlies") or 0)
        total_games = state.total_games

        rng = random.Random(random_seed) if random_seed is not None else random.Random()

        for index in range(1, total_games + 1):
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
                game.current_player = Color.BLACK

            move_cap = 300
            total_time_white = 0.0
            total_time_black = 0.0
            moves_white = 0
            moves_black = 0
            start_time = time.perf_counter()

            for ply in range(move_cap):
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
                decision = controller.select_move(game, cancel_event=state.stop_event)
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

        state.running = False

    def _evaluation_status_payload(self, state: EvaluationState) -> dict[str, Any]:
        white_wins = sum(1 for result in state.results if result.winner == "white")
        black_wins = sum(1 for result in state.results if result.winner == "black")
        draws = sum(1 for result in state.results if result.winner is None)
        total = max(1, len(state.results))
        avg_moves = sum(result.move_count for result in state.results) / total
        avg_duration = sum(result.duration_seconds for result in state.results) / total
        avg_white_time = sum(result.avg_move_time_white for result in state.results) / total
        avg_black_time = sum(result.avg_move_time_black for result in state.results) / total

        return {
            "schema_version": "1.0",
            "evaluationId": state.evaluation_id,
            "running": state.running,
            "completedGames": len(state.results),
            "totalGames": state.total_games,
            "config": state.config,
            "metadata": {
                "variant": state.config.get("variant"),
                "games": state.total_games,
                "startPolicy": state.config.get("startPolicy"),
                "randomSeed": state.config.get("randomSeed"),
                "randomizeOpening": state.config.get("randomizeOpening"),
                "randomizePlies": state.config.get("randomizePlies"),
                "resetConfigsAfterRun": state.config.get("resetConfigsAfterRun"),
                "experimentName": state.config.get("experimentName"),
                "notes": state.config.get("notes"),
                "drawPolicy": state.config.get("drawPolicy"),
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
                "winRateWhite": white_wins / total,
                "winRateBlack": black_wins / total,
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
                for result in state.results
            ],
        }

    def _resolve_parallel_workers(self, color: Color, use_parallel: bool, requested: int) -> int:
        if not use_parallel:
            return 1
        cpu_total = os.cpu_count() or 1
        global_max = max(1, cpu_total - 2)
        other_color = Color.BLACK if color == Color.WHITE else Color.WHITE
        other_settings = self.player_settings.get(other_color, {})
        other_parallel = bool(other_settings.get("parallel"))
        share = max(1, global_max // 2) if other_parallel else global_max
        return min(max(1, requested), share)
