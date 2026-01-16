from __future__ import annotations

import math
import os
import time
import logging
from collections import defaultdict
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor, TimeoutError
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
	use_alpha_beta: bool = True
	use_transposition: bool = True
	use_move_ordering: bool = True
	use_killer_moves: bool = True
	use_quiescence: bool = True
	max_quiescence_depth: int = _MAX_QUIESCENCE_DEPTH


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
_LOGGER = logging.getLogger(__name__)


def clear_transposition_table() -> None:
	"""Reset the global transposition table (useful between games)."""
	_TRANSPOSITION_TABLE.clear()


def select_move(
	game: Game,
	depth: int = 4,
	*,
	use_alpha_beta: bool = True,
	use_transposition: bool = True,
	use_move_ordering: bool = True,
	use_killer_moves: bool = True,
	use_quiescence: bool = True,
	max_quiescence_depth: int = _MAX_QUIESCENCE_DEPTH,
	use_iterative_deepening: bool = False,
	time_limit_ms: int = 1000,
	use_parallel: bool = False,
	workers: int = 1,
) -> Optional[Tuple[Piece, Move]]:
	if depth <= 0:
		raise ValueError("Depth must be positive.")

	options = MinimaxOptions(
		use_alpha_beta=use_alpha_beta,
		use_transposition=use_transposition,
		use_move_ordering=use_move_ordering,
		use_killer_moves=use_killer_moves,
		use_quiescence=use_quiescence,
		max_quiescence_depth=max(1, max_quiescence_depth),
	)

	if _LOGGER.isEnabledFor(logging.DEBUG):
		_LOGGER.debug(
			"Minimax select: depth=%s id=%s time=%sms parallel=%s workers=%s opts=%s",
			depth,
			use_iterative_deepening,
			time_limit_ms,
			use_parallel,
			workers,
			options,
		)

	board = game.board
	player = game.current_player
	moves_map = board.getAllValidMoves(player)
	if not moves_map:
		return None

	ordered_root = _order_moves(
		moves_map,
		board,
		options,
		tt_move=_root_tt_move(board, options),
		killer_moves=defaultdict(list),
		ply=0,
	)
	root_moves = [pair for pair in ordered_root]
	if not root_moves:
		return None

	deadline = None
	if use_iterative_deepening and time_limit_ms > 0:
		deadline = time.perf_counter() + (time_limit_ms / 1000.0)

	best_choice: Optional[Tuple[Piece, Move]] = None
	best_score = -math.inf
	max_depth = depth

	if use_iterative_deepening:
		for current_depth in range(1, max_depth + 1):
			try:
				choice, score, completed = _search_root(
					board,
					player,
					root_moves,
					current_depth,
					options,
					use_parallel=use_parallel,
					workers=workers,
					deadline=deadline,
				)
			except _TimeUp:
				break
			if completed and choice is not None:
				best_choice = choice
				best_score = score
			if deadline is not None and time.perf_counter() >= deadline:
				break
	else:
		best_choice, best_score, _ = _search_root(
			board,
			player,
			root_moves,
			max_depth,
			options,
			use_parallel=use_parallel,
			workers=workers,
			deadline=None,
		)

	return best_choice


class _TimeUp(RuntimeError):
	pass


def _root_tt_move(board: Board, options: MinimaxOptions) -> Optional[Move]:
	if not options.use_transposition:
		return None
	entry = _TRANSPOSITION_TABLE.get(board.compute_hash())
	return entry.best_move if entry else None


def _search_root(
	board: Board,
	player: Color,
	root_moves: List[Tuple[Piece, Move]],
	depth: int,
	options: MinimaxOptions,
	*,
	use_parallel: bool,
	workers: int,
	deadline: Optional[float],
) -> Tuple[Optional[Tuple[Piece, Move]], float, bool]:
	killer_moves: KillerTable = defaultdict(list)
	alpha = -math.inf
	beta = math.inf
	best_score = -math.inf
	best_choice: Optional[Tuple[Piece, Move]] = None

	if use_parallel and len(root_moves) > 1:
		choice, score, completed = _search_root_parallel(
			board,
			player,
			root_moves,
			depth,
			options,
			workers=workers,
			deadline=deadline,
		)
		return choice, score, completed

	for piece, move in root_moves:
		_check_time(deadline)
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
			deadline=deadline,
		)
		if score > best_score + 1e-6:
			best_score = score
			best_choice = (piece, move)
		if options.use_alpha_beta:
			alpha = max(alpha, best_score)
			if alpha >= beta:
				break

	return best_choice, best_score, True


def _search_root_parallel(
	board: Board,
	player: Color,
	root_moves: List[Tuple[Piece, Move]],
	depth: int,
	options: MinimaxOptions,
	*,
	workers: int,
	deadline: Optional[float],
) -> Tuple[Optional[Tuple[Piece, Move]], float, bool]:
	worker_count = _clamp_workers(workers)
	best_score = -math.inf
	best_choice: Optional[Tuple[Piece, Move]] = None
	completed = True

	with ProcessPoolExecutor(max_workers=worker_count) as executor:
		futures = []
		for _, move in root_moves:
			futures.append(
				executor.submit(
					_evaluate_root_move,
					board,
					move,
					depth - 1,
					player,
					options,
					deadline,
				)
			)

		for future in futures:
			try:
				move, score = future.result(timeout=_remaining_time(deadline))
			except TimeoutError:
				completed = False
				break
			except _TimeUp:
				completed = False
				break
			if score > best_score + 1e-6:
				piece = board.getPiece(*move.start)
				if piece is not None:
					best_score = score
					best_choice = (piece, move)

		if not completed:
			for future in futures:
				future.cancel()

	return best_choice, best_score, completed


def _alphabeta(
	board: Board,
	depth: int,
	maximizing_color: Color,
	alpha: float,
	beta: float,
	options: MinimaxOptions,
	killer_moves: KillerTable,
	ply: int,
    deadline: Optional[float],
) -> float:
	_check_time(deadline)
	winner = board.is_game_over()
	if winner is not None:
		if winner == maximizing_color:
			return _WIN_SCORE + depth
		if winner == _opponent(maximizing_color):
			return -_WIN_SCORE - depth
		return 0.0

	if depth == 0:
		if options.use_quiescence:
			return _quiescence(board, maximizing_color, alpha, beta, options, 0, deadline)
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
			if options.use_alpha_beta and alpha >= beta:
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
			_check_time(deadline)
			child = board.simulateMove(move)
			score = _alphabeta(child, depth - 1, maximizing_color, alpha, beta, options, killer_moves, ply + 1, deadline)
			if score > value:
				value = score
				best_move = move
			if options.use_alpha_beta:
				alpha = max(alpha, value)
				if alpha >= beta:
					if options.use_move_ordering and options.use_killer_moves and not move.is_capture:
						_register_killer_move(killer_moves, ply, move)
					break
	else:
		value = math.inf
		for piece, move in ordered_moves:
			_check_time(deadline)
			child = board.simulateMove(move)
			score = _alphabeta(child, depth - 1, maximizing_color, alpha, beta, options, killer_moves, ply + 1, deadline)
			if score < value:
				value = score
				best_move = move
			if options.use_alpha_beta:
				beta = min(beta, value)
				if alpha >= beta:
					if options.use_move_ordering and options.use_killer_moves and not move.is_capture:
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
    deadline: Optional[float],
) -> float:
	_check_time(deadline)
	stand_pat = evaluate_board(board, maximizing_color)
	if options.use_alpha_beta and stand_pat >= beta:
		return beta
	if stand_pat > alpha:
		alpha = stand_pat

	if depth >= options.max_quiescence_depth:
		return stand_pat

	capture_map = _capture_only_moves(board)
	if not capture_map:
		return stand_pat

	ordered = _order_moves(capture_map, board, options, None, defaultdict(list), depth)

	if board.turn == maximizing_color:
		value = stand_pat
		for piece, move in ordered:
			_check_time(deadline)
			child = board.simulateMove(move)
			value = max(value, _quiescence(child, maximizing_color, alpha, beta, options, depth + 1, deadline))
			if options.use_alpha_beta:
				alpha = max(alpha, value)
				if alpha >= beta:
					break
		return value

	value = stand_pat
	for piece, move in ordered:
		_check_time(deadline)
		child = board.simulateMove(move)
		value = min(value, _quiescence(child, maximizing_color, alpha, beta, options, depth + 1, deadline))
		if options.use_alpha_beta:
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
				killer_moves.get(ply, ()) if options.use_killer_moves else (),
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


def _evaluate_root_move(
	board: Board,
	move: Move,
	depth: int,
	maximizing_color: Color,
	options: MinimaxOptions,
	deadline: Optional[float],
) -> Tuple[Move, float]:
	projected = board.simulateMove(move)
	score = _alphabeta(
		projected,
		depth,
		maximizing_color,
		-_alpha_inf(),
		_alpha_inf(),
		options,
		defaultdict(list),
		ply=1,
		deadline=deadline,
	)
	return move, score


def _alpha_inf() -> float:
	return math.inf


def _check_time(deadline: Optional[float]) -> None:
	if deadline is not None and time.perf_counter() >= deadline:
		raise _TimeUp()


def _remaining_time(deadline: Optional[float]) -> Optional[float]:
	if deadline is None:
		return None
	remaining = deadline - time.perf_counter()
	return max(0.0, remaining)


def _clamp_workers(requested: int) -> int:
	cpu_total = os.cpu_count() or 1
	requested = int(requested) if requested is not None else 1
	requested = max(1, requested)
	return min(requested, cpu_total)
