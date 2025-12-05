from __future__ import annotations

from core.board import Board
from core.pieces import Color, Piece


_MAN_VALUE = 1.0
_KING_VALUE = 1.8
_PROGRESS_WEIGHT = 0.1
_CENTER_WEIGHT = 0.08
_BACK_ROW_WEIGHT = 0.12
_MOBILITY_WEIGHT = 0.05
_PROMOTION_WEIGHT = 0.14
_EDGE_WEIGHT = 0.06
_SUPPORT_WEIGHT = 0.07
_CAPTURE_PRESSURE_WEIGHT = 0.04


# Top-level evaluator: combines material, structure, mobility, and tactical pressure.
def evaluate_board(board: Board, perspective: Color) -> float:
	"""Score the position from one side, rewarding material, advancement, central control, safety anchors, teamwork, mobility, and capture pressure."""
	opponent = _opponent(perspective)
	material = {Color.WHITE: 0.0, Color.BLACK: 0.0}
	promotion = {Color.WHITE: 0.0, Color.BLACK: 0.0}
	edges = {Color.WHITE: 0.0, Color.BLACK: 0.0}
	support = {Color.WHITE: 0.0, Color.BLACK: 0.0}

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
		promotion[piece.color] += _promotion_threat(piece, board.boardSize)
		edges[piece.color] += _edge_anchor(piece, board.boardSize)
		support[piece.color] += _support_network(piece, board)

	mobility = _mobility_scores(board)
	capture_pressure = _capture_pressure(board)
	# Convert the accumulated per-color metrics into a perspective score: material,
	# piece advancement, back-rank guards, centralized control, promotion threats,
	# safe edge anchors, supported chains, mobility, and immediate capture pressure.
	score = (
		material[perspective]
		- material[opponent]
		+ _MOBILITY_WEIGHT * (mobility[perspective] - mobility[opponent])
		+ _PROMOTION_WEIGHT * (promotion[perspective] - promotion[opponent])
		+ _EDGE_WEIGHT * (edges[perspective] - edges[opponent])
		+ _SUPPORT_WEIGHT * (support[perspective] - support[opponent])
		+ _CAPTURE_PRESSURE_WEIGHT * (capture_pressure[perspective] - capture_pressure[opponent])
	)
	return score


# Measures how close a man is to promotion (kings always maxed).
def _forward_progress(piece: Piece, size: int) -> float:
	if piece.is_king or size <= 1:
		return 1.0
	max_rank = size - 1
	if piece.color == Color.WHITE:
		return (max_rank - piece.row) / max(max_rank, 1)
	return piece.row / max(max_rank, 1)


# Rewards pieces that sit near the middle files/diagonals.
def _center_bias(piece: Piece, size: int) -> float:
	if size <= 1:
		return 1.0
	center = (size - 1) / 2.0
	max_offset = center if center else 1.0
	delta_row = abs(piece.row - center)
	delta_col = abs(piece.col - center)
	normalized = (delta_row + delta_col) / (2.0 * max_offset)
	return max(0.0, 1.0 - normalized)


# Encourages keeping unmoved pieces on the home rank to block enemy kings.
def _back_rank_guard(piece: Piece, size: int) -> float:
	if piece.is_king:
		return 0.0
	target_row = 0 if piece.color == Color.WHITE else size - 1
	return 1.0 if piece.row == target_row else 0.0


# Counts total legal moves per side to measure freedom of action.
def _mobility_scores(board: Board) -> dict[Color, float]:
	mobility = {Color.WHITE: 0.0, Color.BLACK: 0.0}
	for color in (Color.WHITE, Color.BLACK):
		moves = board.getAllValidMoves(color)
		mobility[color] = float(sum(len(options) for options in moves.values()))
	return mobility


# Scores men that are only a few ranks away from crowning.
def _promotion_threat(piece: Piece, size: int) -> float:
	if piece.is_king or size <= 1:
		return 0.0
	max_rank = size - 1
	target_row = 0 if piece.color == Color.WHITE else max_rank
	distance = abs(piece.row - target_row)
	return max(0.0, 1.0 - distance / max(max_rank, 1))


# Gives credit to pieces protecting the board edges and double corner.
def _edge_anchor(piece: Piece, size: int) -> float:
	if size <= 2:
		return 0.0
	if piece.col in (0, size - 1):
		return 1.0
	if piece.col in (1, size - 2):
		return 0.5
	return 0.0


# Counts friendly diagonal neighbors to encourage tandem formations.
def _support_network(piece: Piece, board: Board) -> float:
	if board.boardSize <= 1:
		return 0.0
	support = 0
	for d_row in (-1, 1):
		for d_col in (-1, 1):
			neighbor = board.getPiece(piece.row + d_row, piece.col + d_col)
			if neighbor and neighbor.color == piece.color:
				support += 1
	return support / 4.0


# Tallies immediate capture options to reflect tactical threats.
def _capture_pressure(board: Board) -> dict[Color, float]:
	pressure = {Color.WHITE: 0.0, Color.BLACK: 0.0}
	for piece in board.getAllPieces():
		moves = piece.possibleMoves(board)
		captures = sum(1 for move in moves if move.is_capture)
		if captures:
			pressure[piece.color] += captures
	return pressure


# Convenience switch between colors.
def _opponent(color: Color) -> Color:
	return Color.BLACK if color == Color.WHITE else Color.WHITE
