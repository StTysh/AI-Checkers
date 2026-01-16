from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from threading import Lock
from typing import Any, Iterable, Optional

from ai.agents import create_minimax_controller, create_simple_minimax_controller, create_mcts_controller
from core.game import Game
from core.move import Move
from core.pieces import Color, Piece
from core.player import PlayerController

from .schemas import AIMoveRequest, ConfigRequest, MoveRequest, PerformAIMoveRequest, ResetRequest, VariantRequest
from .serializers import serialize_game, serialize_move

VARIANT_TO_SIZE = {"british": 8, "international": 10}


def _default_player_settings() -> dict[str, Any]:
    return {
        "type": "human",
        "depth": 4,
        "alphaBeta": True,
        "transposition": False,
        "moveOrdering": True,
        "iterativeDeepening": False,
        "quiescence": False,
        "iterations": 500,
        "rolloutDepth": 80,
        "explorationConstant": 1.4,
        "randomSeed": None,
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


class GameSession:
    """Thread-safe orchestrator around a single Game instance."""

    def __init__(self) -> None:
        self.lock = Lock()
        self.variant = "british"
        self.game = Game(board_size=VARIANT_TO_SIZE[self.variant])
        self.player_settings: dict[Color, dict[str, Any]] = {
            Color.WHITE: _default_player_settings(),
            Color.BLACK: _default_player_settings(),
        }
        self._apply_player_controllers()
        self.pending_ai_moves: dict[Color, Optional[PendingAIMove]] = {
            Color.WHITE: None,
            Color.BLACK: None,
        }

    # public API ---------------------------------------------------------

    def serialize(self) -> dict[str, Any]:
        with self.lock:
            return self._serialize_locked()

    def reset(self, payload: Optional[ResetRequest] = None) -> dict[str, Any]:
        with self.lock:
            if payload and payload.variant:
                self.variant = payload.variant
            self.game.reset(board_size=VARIANT_TO_SIZE[self.variant])
            self._clear_pending_ai_moves()
            self._apply_player_controllers()
            return self._serialize_locked()

    def set_variant(self, payload: VariantRequest) -> dict[str, Any]:
        with self.lock:
            self.variant = payload.variant
            self.game.reset(board_size=VARIANT_TO_SIZE[self.variant])
            self._clear_pending_ai_moves()
            self._apply_player_controllers()
            return self._serialize_locked()

    def configure_players(self, payload: ConfigRequest) -> dict[str, Any]:
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
            self._clear_pending_ai_moves()
            return self._serialize_locked()

    def run_ai_move(self, payload: AIMoveRequest) -> dict[str, Any]:
        with self.lock:
            color = self.game.current_player if payload.color is None else _color_from_label(payload.color)
            if color != self.game.current_player:
                raise ValueError("AI move requested for color that is not on turn.")
            overrides = deepcopy(self.player_settings[color])
            overrides["type"] = payload.algorithm
            if payload.depth is not None:
                overrides["depth"] = payload.depth
            if payload.iterations is not None:
                overrides["iterations"] = payload.iterations
            if payload.rolloutDepth is not None:
                overrides["rolloutDepth"] = payload.rolloutDepth
            if payload.explorationConstant is not None:
                overrides["explorationConstant"] = payload.explorationConstant
            if payload.randomSeed is not None:
                overrides["randomSeed"] = payload.randomSeed
            controller = self._controller_from_settings(color, overrides)
            self.game.setPlayer(color, controller)
            if payload.persist:
                self.player_settings[color] = overrides
            commit_now = payload.commitImmediately
            if not commit_now and self.pending_ai_moves[color]:
                raise RuntimeError("AI move already pending for this color.")

            decision = controller.select_move(self.game)
            if decision is None:
                raise RuntimeError("AI controller could not choose a move.")
            piece, move = decision

            if commit_now:
                self._clear_pending_ai_move(color)
                if not self.game.makeMove(piece, move):
                    raise RuntimeError("Move execution failed.")
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
        with self.lock:
            if not self.game.move_history:
                raise ValueError("No moves to undo.")
            self.game.undoMove()
            self._clear_pending_ai_moves()
            return self._serialize_locked()

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
            return create_minimax_controller(
                label,
                depth=depth,
                use_transposition=bool(settings.get("transposition")),
                use_move_ordering=bool(settings.get("moveOrdering", True)),
                use_quiescence=bool(settings.get("quiescence")),
            )
        if player_type == "minimax_simple":
            depth = int(settings.get("depth") or 4)
            return create_simple_minimax_controller(label, depth=depth)
        if player_type == "mcts":
            iterations = int(settings.get("iterations") or 500)
            rollout_depth = int(settings.get("rolloutDepth") or 80)
            exploration_constant = float(settings.get("explorationConstant") or 1.4)
            random_seed = settings.get("randomSeed")
            return create_mcts_controller(
                label,
                iterations=iterations,
                rollout_depth=rollout_depth,
                exploration_constant=exploration_constant,
                random_seed=random_seed,
            )
        raise ValueError(f"Player type '{player_type}' not implemented yet.")
