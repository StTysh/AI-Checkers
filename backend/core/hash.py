from __future__ import annotations

import random
from typing import Dict, Tuple, TYPE_CHECKING

from .pieces import Color, Piece

if TYPE_CHECKING:  # pragma: no cover
    from .board import Board

_RANDOM_SEED = 20241129
_PIECE_VARIANTS = ("white_man", "white_king", "black_man", "black_king")
_ZOBRIST_TABLE: Dict[int, Dict[Tuple[int, int, str], int]] = {}
_TURN_KEYS = {
    Color.WHITE: random.Random(_RANDOM_SEED).getrandbits(64),
    Color.BLACK: random.Random(_RANDOM_SEED + 1).getrandbits(64),
}


def _piece_variant(piece: Piece) -> str:
    role = "king" if piece.is_king else "man"
    return f"{piece.color.value}_{role}"


def _table_for_size(board_size: int) -> Dict[Tuple[int, int, str], int]:
    table = _ZOBRIST_TABLE.get(board_size)
    if table is not None:
        return table

    rng = random.Random(_RANDOM_SEED + board_size)
    table = {
        (row, col, variant): rng.getrandbits(64)
        for row in range(board_size)
        for col in range(board_size)
        for variant in _PIECE_VARIANTS
    }
    _ZOBRIST_TABLE[board_size] = table
    return table


def compute_board_hash(board: "Board") -> int:
    """Return a Zobrist hash for the current board layout and player to move."""

    table = _table_for_size(board.boardSize)
    result = _TURN_KEYS[board.turn]

    for row in range(board.boardSize):
        for col in range(board.boardSize):
            piece = board.board[row][col]
            if piece is None:
                continue
            result ^= table[(row, col, _piece_variant(piece))]

    return result
