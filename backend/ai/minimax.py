from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, auto
from typing import DefaultDict, Dict, Iterable, List, Optional, Tuple

from core.board import Board
from core.game import Game
from core.move import Move
from core.pieces import Color, Piece

from .huistic import evaluate_board

_WIN_SCORE = 1_000_000.0
_MAX_TT_ENTRIES = 500_000
_MAX_QUIESCENCE_DEPTH = 6


@dataclass(frozen=True)
class MinimaxOptions:
	use_transposition: bool = True
	use_move_ordering: bool = True
	use_quiescence: bool = True


class Bound(Enum):
	EXACT = auto()
	LOWER = auto()
	UPPER = auto()


@dataclass
class TTEntry:
	key: int
	depth: int
	score: float
	flag: Bound
	best_move: Optional[Move]


TranspositionTable = Dict[int, TTEntry]
KillerTable = DefaultDict[int, List[Move]]

_TRANSPOSITION_TABLE: TranspositionTable = {}


def clear_transposition_table() -> None:
	"""Reset the global transposition table (useful between games)."""
	_TRANSPOSITION_TABLE.clear()


def select_move(
	game: Game,
	depth: int = 4,
	*,
	use_transposition: bool = True,
	use_move_ordering: bool = True,
	use_quiescence: bool = True,
) -> Optional[Tuple[Piece, Move]]:
	if depth <= 0:
		raise ValueError("Depth must be positive.")

	options = MinimaxOptions(
		use_transposition=use_transposition,
		use_move_ordering=use_move_ordering,
		use_quiescence=use_quiescence,
	)

	board = game.board
	player = game.current_player
	moves_map = board.getAllValidMoves(player)
	if not moves_map:
		return None

	killer_moves: KillerTable = defaultdict(list)
	alpha = -math.inf
	beta = math.inf
	best_score = -math.inf
	best_choice: Optional[Tuple[Piece, Move]] = None

	tt_move = None
	if options.use_transposition:
		tt_entry = _TRANSPOSITION_TABLE.get(board.compute_hash())
		if tt_entry:
			tt_move = tt_entry.best_move

	ordered_moves = _order_moves(
		moves_map,
		board,
		options,
		tt_move,
		killer_moves,
		ply=0,
	)

	for piece, move in ordered_moves:
		projected = board.simulateMove(move)
		score = _alphabeta(
			projected,
			depth - 1,
			player,
			alpha,
			beta,
			options,
			killer_moves,
			ply=1,
		)
		if score > best_score + 1e-6:
			best_score = score
			best_choice = (piece, move)
		alpha = max(alpha, best_score)
		if alpha >= beta:
			break

	return best_choice


def _alphabeta(
	board: Board,
	depth: int,
	maximizing_color: Color,
	alpha: float,
	beta: float,
	options: MinimaxOptions,
	killer_moves: KillerTable,
	ply: int,
) -> float:
	winner = board.is_game_over()
	if winner is not None:
		if winner == maximizing_color:
			return _WIN_SCORE + depth
		if winner == _opponent(maximizing_color):
			return -_WIN_SCORE - depth
		return 0.0

	if depth == 0:
		if options.use_quiescence:
			return _quiescence(board, maximizing_color, alpha, beta, options, 0)
		return evaluate_board(board, maximizing_color)

	moves_map = board.getAllValidMoves(board.turn)
	if not moves_map:
		return evaluate_board(board, maximizing_color)

	alpha_orig = alpha
	beta_orig = beta
	best_move: Optional[Move] = None
	board_hash = board.compute_hash() if options.use_transposition else None
	tt_entry = None

	if options.use_transposition and board_hash is not None:
		tt_entry = _TRANSPOSITION_TABLE.get(board_hash)
		if tt_entry and tt_entry.depth >= depth:
			if tt_entry.flag == Bound.EXACT:
				return tt_entry.score
			if tt_entry.flag == Bound.LOWER:
				alpha = max(alpha, tt_entry.score)
			elif tt_entry.flag == Bound.UPPER:
				beta = min(beta, tt_entry.score)
			if alpha >= beta:
				return tt_entry.score

	ordered_moves = _order_moves(
		moves_map,
		board,
		options,
		tt_entry.best_move if tt_entry else None,
		killer_moves,
		ply,
	)

	if board.turn == maximizing_color:
		value = -math.inf
		for piece, move in ordered_moves:
			child = board.simulateMove(move)
			score = _alphabeta(child, depth - 1, maximizing_color, alpha, beta, options, killer_moves, ply + 1)
			if score > value:
				value = score
				best_move = move
			alpha = max(alpha, value)
			if alpha >= beta:
				if options.use_move_ordering and not move.is_capture:
					_register_killer_move(killer_moves, ply, move)
				break
	else:
		value = math.inf
		for piece, move in ordered_moves:
			child = board.simulateMove(move)
			score = _alphabeta(child, depth - 1, maximizing_color, alpha, beta, options, killer_moves, ply + 1)
			if score < value:
				value = score
				best_move = move
			beta = min(beta, value)
			if alpha >= beta:
				if options.use_move_ordering and not move.is_capture:
					_register_killer_move(killer_moves, ply, move)
				break

	if options.use_transposition and board_hash is not None:
		_store_tt_entry(board_hash, depth, value, alpha_orig, beta_orig, best_move)

	return value


def _quiescence(
	board: Board,
	maximizing_color: Color,
	alpha: float,
	beta: float,
	options: MinimaxOptions,
	depth: int,
) -> float:
	stand_pat = evaluate_board(board, maximizing_color)
	if stand_pat >= beta:
		return beta
	if stand_pat > alpha:
		alpha = stand_pat

	if depth >= _MAX_QUIESCENCE_DEPTH:
		return stand_pat

	capture_map = _capture_only_moves(board)
	if not capture_map:
		return stand_pat

	ordered = _order_moves(capture_map, board, options, None, defaultdict(list), depth)

	if board.turn == maximizing_color:
		value = stand_pat
		for piece, move in ordered:
			child = board.simulateMove(move)
			value = max(value, _quiescence(child, maximizing_color, alpha, beta, options, depth + 1))
			alpha = max(alpha, value)
			if alpha >= beta:
				break
		return value

	value = stand_pat
	for piece, move in ordered:
		child = board.simulateMove(move)
		value = min(value, _quiescence(child, maximizing_color, alpha, beta, options, depth + 1))
		beta = min(beta, value)
		if alpha >= beta:
			break
	return value


def _order_moves(
	moves_map: dict[Piece, List[Move]],
	board: Board,
	options: MinimaxOptions,
	tt_move: Optional[Move],
	killer_moves: KillerTable,
	ply: int,
) -> List[Tuple[Piece, Move]]:
	if not options.use_move_ordering:
		return [(piece, move) for piece, moves in moves_map.items() for move in moves]

	scored: List[Tuple[float, Tuple[Piece, Move]]] = []
	for piece, moves in moves_map.items():
		for move in moves:
			pair = (piece, move)
			score = _move_sort_score(
				piece,
				move,
				board.boardSize,
				tt_move,
				killer_moves.get(ply, ()),
			)
			scored.append((score, pair))

	scored.sort(key=lambda item: item[0], reverse=True)
	return [pair for _, pair in scored]


def _move_sort_score(
	piece: Piece,
	move: Move,
	board_size: int,
	tt_move: Optional[Move],
	killers: Iterable[Move],
) -> float:
	score = 0.0
	if move == tt_move:
		score += 1_000.0
	if move.is_capture:
		score += 500.0 + len(move.captures) * 25.0
	if _would_promote(piece, move, board_size):
		score += 150.0
	if move in killers:
		score += 120.0
	return score


def _would_promote(piece: Piece, move: Move, board_size: int) -> bool:
	if piece.is_king:
		return False
	last_row = 0 if piece.color == Color.WHITE else board_size - 1
	return move.end[0] == last_row


def _capture_only_moves(board: Board) -> dict[Piece, List[Move]]:
	moves_map = board.getAllValidMoves(board.turn)
	if not moves_map:
		return {}
	first_moves = next(iter(moves_map.values()), None)
	if first_moves and first_moves[0].is_capture:
		return moves_map
	captures: dict[Piece, List[Move]] = {}
	for piece, moves in moves_map.items():
		capture_moves = [move for move in moves if move.is_capture]
		if capture_moves:
			captures[piece] = capture_moves
	return captures


def _register_killer_move(killer_moves: KillerTable, ply: int, move: Move) -> None:
	moves = killer_moves[ply]
	if move in moves:
		return
	moves.append(move)
	if len(moves) > 2:
		moves.pop(0)


def _store_tt_entry(
	key: int,
	depth: int,
	score: float,
	alpha_orig: float,
	beta_orig: float,
	best_move: Optional[Move],
) -> None:
	if len(_TRANSPOSITION_TABLE) >= _MAX_TT_ENTRIES:
		_TRANSPOSITION_TABLE.pop(next(iter(_TRANSPOSITION_TABLE)))
	if score <= alpha_orig:
		flag = Bound.UPPER
	elif score >= beta_orig:
		flag = Bound.LOWER
	else:
		flag = Bound.EXACT
	_TRANSPOSITION_TABLE[key] = TTEntry(key, depth, score, flag, best_move)


def _opponent(color: Color) -> Color:
	return Color.BLACK if color == Color.WHITE else Color.WHITE
