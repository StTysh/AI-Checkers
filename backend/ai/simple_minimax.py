from __future__ import annotations

import math
from typing import Iterable, Iterator, Optional, Tuple

from core.board import Board
from core.game import Game
from core.move import Move
from core.pieces import Color, Piece

from .huistic import evaluate_board

_WIN_SCORE = 1_000_000.0


def select_move(game: Game, depth: int = 4) -> Optional[Tuple[Piece, Move]]:
	"""Return the best move found by a plain alpha-beta minimax search."""
	if depth <= 0:
		raise ValueError("Depth must be positive.")

	board = game.board
	player = game.current_player
	moves_map = board.getAllValidMoves(player)
	if not moves_map:
		return None

	alpha = -math.inf
	beta = math.inf
	best_score = -math.inf
	best_choice: Optional[Tuple[Piece, Move]] = None

	for piece, move in _iter_moves(moves_map):
		child = board.simulateMove(move)
		score = _alphabeta(child, depth - 1, player, alpha, beta)
		if score > best_score + 1e-6:
			best_score = score
			best_choice = (piece, move)
		alpha = max(alpha, best_score)
		if alpha >= beta:
			break

	return best_choice

def _alphabeta(board: Board, depth: int, maximizing_color: Color, alpha: float, beta: float) -> float:
	winner = board.is_game_over()
	if winner is not None:
		if winner == maximizing_color:
			return _WIN_SCORE + depth
		if winner == _opponent(maximizing_color):
			return -_WIN_SCORE - depth
		return 0.0

	if depth == 0:
		return evaluate_board(board, maximizing_color)

	moves_map = board.getAllValidMoves(board.turn)
	if not moves_map:
		return evaluate_board(board, maximizing_color)

	if board.turn == maximizing_color:
		value = -math.inf
		for piece, move in _iter_moves(moves_map):
			child = board.simulateMove(move)
			value = max(value, _alphabeta(child, depth - 1, maximizing_color, alpha, beta))
			alpha = max(alpha, value)
			if alpha >= beta:
				break
		return value

	value = math.inf
	for piece, move in _iter_moves(moves_map):
		child = board.simulateMove(move)
		value = min(value, _alphabeta(child, depth - 1, maximizing_color, alpha, beta))
		beta = min(beta, value)
		if alpha >= beta:
			break
	return value


def _iter_moves(moves_map: dict[Piece, Iterable[Move]]) -> Iterator[Tuple[Piece, Move]]:
	for piece, moves in moves_map.items():
		for move in moves:
			yield piece, move


def _opponent(color: Color) -> Color:
	return Color.BLACK if color == Color.WHITE else Color.WHITE
