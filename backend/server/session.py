from __future__ import annotations

from copy import deepcopy
from threading import Lock
from typing import Any, Iterable, Optional

from ai.agents import create_minimax_controller
from core.game import Game
from core.move import Move
from core.pieces import Color, Piece
from core.player import PlayerController

from .schemas import AIMoveRequest, ConfigRequest, MoveRequest, ResetRequest, VariantRequest
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
    }


def _color_from_label(label: str) -> Color:
    try:
        return Color[label.upper()]
    except KeyError as exc:
        raise ValueError(f"Unsupported color '{label}'.") from exc


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

    # public API ---------------------------------------------------------

    def serialize(self) -> dict[str, Any]:
        with self.lock:
            return self._serialize_locked()

    def reset(self, payload: Optional[ResetRequest] = None) -> dict[str, Any]:
        with self.lock:
            if payload and payload.variant:
                self.variant = payload.variant
            self.game.reset(board_size=VARIANT_TO_SIZE[self.variant])
            self._apply_player_controllers()
            return self._serialize_locked()

    def set_variant(self, payload: VariantRequest) -> dict[str, Any]:
        with self.lock:
            self.variant = payload.variant
            self.game.reset(board_size=VARIANT_TO_SIZE[self.variant])
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
            controller = self._controller_from_settings(color, overrides)
            self.game.setPlayer(color, controller)
            if payload.persist:
                self.player_settings[color] = overrides
            if not self.game.requestAIMove():
                raise RuntimeError("AI controller could not choose a move.")
            return self._serialize_locked()

    # helpers ------------------------------------------------------------

    def _serialize_locked(self) -> dict[str, Any]:
        return serialize_game(self.game, self.variant, self.player_settings)

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
            return create_minimax_controller(f"{label} Minimax", depth=depth)
        raise ValueError(f"Player type '{player_type}' not implemented yet.")
