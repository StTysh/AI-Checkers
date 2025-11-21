from __future__ import annotations

from core.board import Board
from core.pieces import Color, Piece


_MAN_VALUE = 1.0
_KING_VALUE = 1.8
_PROGRESS_WEIGHT = 0.1
_CENTER_WEIGHT = 0.08
_BACK_ROW_WEIGHT = 0.12
_MOBILITY_WEIGHT = 0.05


def evaluate_board(board: Board, perspective: Color) -> float:
	opponent = _opponent(perspective)
	material = {Color.WHITE: 0.0, Color.BLACK: 0.0}

	for piece in board.getAllPieces():
		base = _KING_VALUE if piece.is_king else _MAN_VALUE
		progress = _forward_progress(piece, board.boardSize)
		centricity = _center_bias(piece, board.boardSize)
		guard = _back_rank_guard(piece, board.boardSize)
		material[piece.color] += (
			base
			+ _PROGRESS_WEIGHT * progress
			+ _CENTER_WEIGHT * centricity
			+ _BACK_ROW_WEIGHT * guard
		)

	mobility = _mobility_scores(board)
	score = (
		material[perspective]
		- material[opponent]
		+ _MOBILITY_WEIGHT * (mobility[perspective] - mobility[opponent])
	)
	return score


def _forward_progress(piece: Piece, size: int) -> float:
	if piece.is_king or size <= 1:
		return 1.0
	max_rank = size - 1
	if piece.color == Color.WHITE:
		return (max_rank - piece.row) / max(max_rank, 1)
	return piece.row / max(max_rank, 1)


def _center_bias(piece: Piece, size: int) -> float:
	if size <= 1:
		return 1.0
	center = (size - 1) / 2.0
	max_offset = center if center else 1.0
	delta_row = abs(piece.row - center)
	delta_col = abs(piece.col - center)
	normalized = (delta_row + delta_col) / (2.0 * max_offset)
	return max(0.0, 1.0 - normalized)


def _back_rank_guard(piece: Piece, size: int) -> float:
	if piece.is_king:
		return 0.0
	target_row = 0 if piece.color == Color.WHITE else size - 1
	return 1.0 if piece.row == target_row else 0.0


def _mobility_scores(board: Board) -> dict[Color, float]:
	mobility = {Color.WHITE: 0.0, Color.BLACK: 0.0}
	for color in (Color.WHITE, Color.BLACK):
		moves = board.getAllValidMoves(color)
		mobility[color] = float(sum(len(options) for options in moves.values()))
	return mobility


def _opponent(color: Color) -> Color:
	return Color.BLACK if color == Color.WHITE else Color.WHITE
