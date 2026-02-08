from __future__ import annotations

from dataclasses import dataclass

from core.board import Board
from core.pieces import Color, Piece


@dataclass(frozen=True, slots=True)
class EvalProfile:
	man_value: float
	king_value_open: float
	king_value_end: float
	progress_weight: float
	center_weight: float
	back_row_weight_open: float
	back_row_weight_end: float
	mobility_weight: float
	promotion_weight_open: float
	promotion_weight_end: float
	edge_weight: float
	support_weight: float
	capture_pressure_weight: float
	threat_weight: float
	capture_opportunity_weight: float


_PROFILE_8 = EvalProfile(
	man_value=1.0,
	king_value_open=2.05,
	king_value_end=2.35,
	progress_weight=0.12,
	center_weight=0.08,
	back_row_weight_open=0.22,
	back_row_weight_end=0.06,
	mobility_weight=0.04,
	promotion_weight_open=0.10,
	promotion_weight_end=0.22,
	edge_weight=0.04,
	support_weight=0.06,
	capture_pressure_weight=0.03,
	threat_weight=0.35,
	capture_opportunity_weight=0.18,
)

_PROFILE_10 = EvalProfile(
	man_value=1.0,
	king_value_open=2.65,  # flying kings are stronger
	king_value_end=3.10,
	progress_weight=0.06,
	center_weight=0.06,
	back_row_weight_open=0.14,
	back_row_weight_end=0.04,
	mobility_weight=0.06,
	promotion_weight_open=0.08,
	promotion_weight_end=0.18,
	edge_weight=0.02,
	support_weight=0.05,
	capture_pressure_weight=0.04,
	threat_weight=0.45,
	capture_opportunity_weight=0.22,
)


def _profile_for(board_size: int) -> EvalProfile:
	return _PROFILE_8 if board_size == 8 else _PROFILE_10


def _starting_pieces_per_side(board_size: int) -> int:
	# Standard draughts setup on even-sized boards: (N/2 - 1) rows filled per side,
	# with N/2 playable dark squares per row.
	half = max(1, board_size // 2)
	return max(0, (half - 1) * half)


def _phase(board: Board) -> float:
	# 0.0 = opening, 1.0 = endgame.
	start_total = 2 * _starting_pieces_per_side(board.boardSize)
	if start_total <= 0:
		return 0.5
	pieces_now = len(board.getAllPieces())
	return max(0.0, min(1.0, 1.0 - (pieces_now / start_total)))


# Top-level evaluator: combines material, structure, mobility, and tactical pressure.
def evaluate_board(board: Board, perspective: Color) -> float:
	"""Score the position from one side, rewarding material, advancement, central control, safety anchors, teamwork, mobility, and capture pressure."""
	profile = _profile_for(board.boardSize)
	phase = _phase(board)
	king_value = profile.king_value_open + (profile.king_value_end - profile.king_value_open) * phase
	back_row_weight = profile.back_row_weight_open + (profile.back_row_weight_end - profile.back_row_weight_open) * phase
	promotion_weight = profile.promotion_weight_open + (profile.promotion_weight_end - profile.promotion_weight_open) * phase

	opponent = _opponent(perspective)
	pieces = board.getAllPieces()
	by_pos = {(piece.row, piece.col): piece for piece in pieces}

	material = {Color.WHITE: 0.0, Color.BLACK: 0.0}
	progress = {Color.WHITE: 0.0, Color.BLACK: 0.0}
	centers = {Color.WHITE: 0.0, Color.BLACK: 0.0}
	back_row = {Color.WHITE: 0.0, Color.BLACK: 0.0}
	promotion = {Color.WHITE: 0.0, Color.BLACK: 0.0}
	edges = {Color.WHITE: 0.0, Color.BLACK: 0.0}
	support = {Color.WHITE: 0.0, Color.BLACK: 0.0}

	for piece in pieces:
		if piece.is_king:
			material[piece.color] += king_value
		else:
			material[piece.color] += profile.man_value
			progress[piece.color] += _forward_progress(piece, board.boardSize)
			promotion[piece.color] += _promotion_threat(piece, board.boardSize)
			back_row[piece.color] += _back_rank_guard(piece, board.boardSize)

		centers[piece.color] += _center_bias(piece, board.boardSize)
		edges[piece.color] += _edge_anchor(piece, board.boardSize)
		support[piece.color] += _support_network(piece, board)

	# Use the (cached) legal move generator for mobility / pressure so the evaluator
	# matches forced-capture and (10x10) majority-capture rules.
	moves_map = {
		Color.WHITE: board.getAllValidMoves(Color.WHITE),
		Color.BLACK: board.getAllValidMoves(Color.BLACK),
	}
	mobility = {Color.WHITE: 0.0, Color.BLACK: 0.0}
	capture_pressure = {Color.WHITE: 0.0, Color.BLACK: 0.0}
	for color in (Color.WHITE, Color.BLACK):
		legal = moves_map[color]
		if not legal:
			continue
		mobility[color] = float(sum(len(options) for options in legal.values()))
		pressure = 0.0
		for options in legal.values():
			for move in options:
				if move.is_capture:
					pressure += 1.0 + 0.20 * len(move.captures)
		capture_pressure[color] = pressure

	def capture_targets(color: Color) -> set[tuple[int, int]]:
		targets: set[tuple[int, int]] = set()
		for options in moves_map[color].values():
			for move in options:
				for cap in move.captures:
					targets.add(cap)
		return targets

	white_targets = capture_targets(Color.WHITE)
	black_targets = capture_targets(Color.BLACK)
	threatened = {
		Color.WHITE: float(sum(1 for pos in black_targets if by_pos.get(pos) and by_pos[pos].color == Color.WHITE)),
		Color.BLACK: float(sum(1 for pos in white_targets if by_pos.get(pos) and by_pos[pos].color == Color.BLACK)),
	}
	capture_opportunity = {
		Color.WHITE: float(sum(1 for pos in white_targets if by_pos.get(pos) and by_pos[pos].color == Color.BLACK)),
		Color.BLACK: float(sum(1 for pos in black_targets if by_pos.get(pos) and by_pos[pos].color == Color.WHITE)),
	}

	score = (
		(material[perspective] - material[opponent])
		+ profile.progress_weight * (progress[perspective] - progress[opponent])
		+ profile.center_weight * (centers[perspective] - centers[opponent])
		+ back_row_weight * (back_row[perspective] - back_row[opponent])
		+ promotion_weight * (promotion[perspective] - promotion[opponent])
		+ profile.edge_weight * (edges[perspective] - edges[opponent])
		+ profile.support_weight * (support[perspective] - support[opponent])
		+ profile.mobility_weight * (mobility[perspective] - mobility[opponent])
		+ profile.capture_pressure_weight * (capture_pressure[perspective] - capture_pressure[opponent])
		+ profile.capture_opportunity_weight * (capture_opportunity[perspective] - capture_opportunity[opponent])
		- profile.threat_weight * (threatened[perspective] - threatened[opponent])
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
	# Home rank is the *starting* rank, not the promotion rank.
	target_row = size - 1 if piece.color == Color.WHITE else 0
	return 1.0 if piece.row == target_row else 0.0


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


# Convenience switch between colors.
def _opponent(color: Color) -> Color:
	return Color.BLACK if color == Color.WHITE else Color.WHITE
