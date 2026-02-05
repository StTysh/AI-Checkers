from __future__ import annotations

import math
import os
import time
import logging
import multiprocessing as mp
from collections import defaultdict
from dataclasses import dataclass, replace
from multiprocessing.context import BaseContext
from multiprocessing.pool import Pool
from multiprocessing import TimeoutError as MPTimeoutError
from enum import Enum, auto
from threading import Event
from typing import DefaultDict, Dict, Iterable, List, Optional, Tuple

from core.board import Board
from core.game import Game
from core.move import Move
from core.pieces import Color, Piece
from core.hash import zobrist_turn_key

from .huistic import evaluate_board
from .cancel import CancelledError, raise_if_cancelled

_WIN_SCORE = 1_000_000.0
_MAX_TT_ENTRIES = 500_000
_MAX_QUIESCENCE_DEPTH = 6
_DEFAULT_ASPIRATION_WINDOW = 50.0
_DEFAULT_ENDGAME_MAX_PIECES = 6
_DEFAULT_ENDGAME_MAX_PLIES = 40


@dataclass(frozen=True)
class MinimaxOptions:
	use_alpha_beta: bool = True
	use_transposition: bool = True
	use_move_ordering: bool = True
	use_killer_moves: bool = True
	use_quiescence: bool = True
	max_quiescence_depth: int = _MAX_QUIESCENCE_DEPTH
	use_aspiration: bool = False
	aspiration_window: float = _DEFAULT_ASPIRATION_WINDOW
	use_history_heuristic: bool = False
	use_butterfly_heuristic: bool = False
	use_null_move: bool = False
	null_move_reduction: int = 2
	use_lmr: bool = False
	lmr_min_depth: int = 3
	lmr_min_moves: int = 4
	lmr_reduction: int = 1
	deterministic_ordering: bool = True
	use_endgame_tablebase: bool = False
	endgame_max_pieces: int = _DEFAULT_ENDGAME_MAX_PIECES
	endgame_max_plies: int = _DEFAULT_ENDGAME_MAX_PLIES


class Bound(Enum):
	EXACT = auto()
	LOWER = auto()
	UPPER = auto()


@dataclass
class TTEntry:
	key: tuple[int, Color]
	depth: int
	score: float
	flag: Bound
	best_move: Optional[Move]


TranspositionTable = Dict[tuple[int, Color], TTEntry]
KillerTable = DefaultDict[int, List[Move]]
HistoryTable = DefaultDict[Tuple[int, int, int, int, int], int]
ButterflyTable = DefaultDict[Tuple[int, int, int, int, int], int]

_TRANSPOSITION_TABLE: TranspositionTable = {}
_ENDGAME_TABLEBASE: Dict[Tuple[int, Color], float] = {}
_LOGGER = logging.getLogger(__name__)
_MP_CTX: Optional[BaseContext] = None


def _mp_ctx() -> BaseContext:
	global _MP_CTX
	if _MP_CTX is None:
		_MP_CTX = mp.get_context("spawn")
	return _MP_CTX


def _root_worker(
	board_state,
	move: Move,
	depth: int,
	maximizing_color: Color,
	options: "MinimaxOptions",
	history_table: dict,
	butterfly_table: dict,
	alpha: float,
	beta: float,
	deadline: Optional[float],
) -> Tuple[Move, float]:
	board = Board.from_state(board_state)
	return _evaluate_root_move(
		board,
		move,
		depth,
		maximizing_color,
		options,
		defaultdict(int, history_table),
		defaultdict(int, butterfly_table),
		alpha,
		beta,
		deadline,
		None,
	)


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
	use_aspiration: bool = False,
	aspiration_window: float = _DEFAULT_ASPIRATION_WINDOW,
	use_history_heuristic: bool = False,
	use_butterfly_heuristic: bool = False,
	use_null_move: bool = False,
	null_move_reduction: int = 2,
	use_lmr: bool = False,
	lmr_min_depth: int = 3,
	lmr_min_moves: int = 4,
	lmr_reduction: int = 1,
	deterministic_ordering: bool = True,
	use_endgame_tablebase: bool = False,
	endgame_max_pieces: int = _DEFAULT_ENDGAME_MAX_PIECES,
	endgame_max_plies: int = _DEFAULT_ENDGAME_MAX_PLIES,
	use_iterative_deepening: bool = False,
	time_limit_ms: int = 1000,
	use_parallel: bool = False,
	workers: int = 1,
	cancel_event: Optional[Event] = None,
) -> Optional[Tuple[Piece, Move]]:
	if depth <= 0:
		raise ValueError("Depth must be positive.")

	raise_if_cancelled(cancel_event)

	options = MinimaxOptions(
		use_alpha_beta=use_alpha_beta,
		use_transposition=use_transposition,
		use_move_ordering=use_move_ordering,
		use_killer_moves=use_killer_moves,
		use_quiescence=use_quiescence,
		max_quiescence_depth=max(1, max_quiescence_depth),
		use_aspiration=use_aspiration,
		aspiration_window=max(1.0, aspiration_window),
		use_history_heuristic=use_history_heuristic,
		use_butterfly_heuristic=use_butterfly_heuristic,
		use_null_move=use_null_move,
		null_move_reduction=max(1, null_move_reduction),
		use_lmr=use_lmr,
		lmr_min_depth=max(1, lmr_min_depth),
		lmr_min_moves=max(1, lmr_min_moves),
		lmr_reduction=max(1, lmr_reduction),
		deterministic_ordering=deterministic_ordering,
		use_endgame_tablebase=use_endgame_tablebase,
		endgame_max_pieces=max(2, endgame_max_pieces),
		endgame_max_plies=max(2, endgame_max_plies),
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

	history_table: HistoryTable = defaultdict(int)
	butterfly_table: ButterflyTable = defaultdict(int)

	ordered_root = _order_moves(
		moves_map,
		board,
		options,
		tt_move=_root_tt_move(board, player, options),
		killer_moves=defaultdict(list),
		history_table=history_table,
		butterfly_table=butterfly_table,
		ply=0,
	)
	root_moves = [pair for pair in ordered_root]
	if not root_moves:
		return None

	deadline = None
	if time_limit_ms > 0:
		deadline = time.perf_counter() + (time_limit_ms / 1000.0)

	best_choice: Optional[Tuple[Piece, Move]] = None
	best_score = -math.inf
	max_depth = depth

	if use_iterative_deepening:
		for current_depth in range(1, max_depth + 1):
			raise_if_cancelled(cancel_event)
			alpha = -math.inf
			beta = math.inf
			window = options.aspiration_window
			if options.use_aspiration and best_score > -math.inf / 2:
				alpha = best_score - window
				beta = best_score + window
			try:
				while True:
					parallel_now = use_parallel and current_depth == max_depth
					choice, score, completed = _search_root(
						board,
						player,
						root_moves,
						current_depth,
						options,
						history_table,
						butterfly_table,
						alpha=alpha,
						beta=beta,
						use_parallel=parallel_now,
						workers=workers,
						deadline=deadline,
						cancel_event=cancel_event,
					)
					if not options.use_aspiration or not completed:
						break
					if score <= alpha:
						window *= 2
						alpha = best_score - window
						beta = best_score + window
						continue
					if score >= beta:
						window *= 2
						alpha = best_score - window
						beta = best_score + window
						continue
					break
			except _TimeUp:
				break
			except CancelledError:
				raise
			if choice is not None:
				if completed or best_choice is None:
					best_choice = choice
					best_score = score
			if not completed:
				break
			if deadline is not None and time.perf_counter() >= deadline:
				break
	else:
		best_choice, best_score, _ = _search_root(
			board,
			player,
			root_moves,
			max_depth,
			options,
			history_table,
			butterfly_table,
			alpha=-math.inf,
			beta=math.inf,
			use_parallel=use_parallel,
			workers=workers,
			deadline=deadline,
			cancel_event=cancel_event,
		)

	return best_choice


class _TimeUp(RuntimeError):
	pass


def _root_tt_move(board: Board, maximizing_color: Color, options: MinimaxOptions) -> Optional[Move]:
	if not options.use_transposition:
		return None
	entry = _TRANSPOSITION_TABLE.get((board.compute_hash(), maximizing_color))
	return entry.best_move if entry else None


def _search_root(
	board: Board,
	player: Color,
	root_moves: List[Tuple[Piece, Move]],
	depth: int,
	options: MinimaxOptions,
	history_table: HistoryTable,
	butterfly_table: ButterflyTable,
	*,
	alpha: float,
	beta: float,
	use_parallel: bool,
	workers: int,
	deadline: Optional[float],
	cancel_event: Optional[Event],
) -> Tuple[Optional[Tuple[Piece, Move]], float, bool]:
	killer_moves: KillerTable = defaultdict(list)
	best_score = -math.inf
	best_choice: Optional[Tuple[Piece, Move]] = root_moves[0] if root_moves else None

	if use_parallel and len(root_moves) > 1:
		choice, score, completed = _search_root_parallel(
			board,
			player,
			root_moves,
			depth,
			options,
			history_table,
			butterfly_table,
			alpha=alpha,
			beta=beta,
			workers=workers,
			deadline=deadline,
			cancel_event=cancel_event,
		)
		return choice, score, completed

	for piece, move in root_moves:
		try:
			_check_time(deadline, cancel_event)
		except _TimeUp:
			return best_choice, best_score, False
		undo = board.make_move(piece, move)
		try:
			try:
				score = _alphabeta(
					board,
					depth - 1,
					player,
					alpha,
					beta,
					options,
					killer_moves,
					history_table,
					butterfly_table,
					ply=1,
					deadline=deadline,
					cancel_event=cancel_event,
				)
			except _TimeUp:
				return best_choice, best_score, False
		finally:
			board.unmake_move(undo)
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
	history_table: HistoryTable,
	butterfly_table: ButterflyTable,
	*,
	alpha: float,
	beta: float,
	workers: int,
	deadline: Optional[float],
	cancel_event: Optional[Event],
) -> Tuple[Optional[Tuple[Piece, Move]], float, bool]:
	worker_count = min(_clamp_workers(workers), max(1, len(root_moves)))
	best_score = -math.inf
	best_choice: Optional[Tuple[Piece, Move]] = root_moves[0] if root_moves else None
	completed = True

	ctx = _mp_ctx()

	board_state = board.to_state()
	history_snapshot = dict(history_table)
	butterfly_snapshot = dict(butterfly_table)

	pool: Pool | None = None
	try:
		pool = ctx.Pool(processes=worker_count, maxtasksperchild=1)
		results = [
			pool.apply_async(
				_root_worker,
				(
					board_state,
					move,
					depth - 1,
					player,
					options,
					history_snapshot,
					butterfly_snapshot,
					alpha,
					beta,
					deadline,
				),
			)
			for _, move in root_moves
		]

		pending = list(results)
		while pending:
			try:
				_check_time(deadline, cancel_event)
			except _TimeUp:
				completed = False
				pool.terminate()
				pool.join()
				return best_choice, best_score, completed

			next_pending = []
			for async_result in pending:
				remaining = _remaining_time(deadline)
				timeout = 0.05 if remaining is None else max(0.0, min(0.05, remaining))
				try:
					move, score = async_result.get(timeout=timeout)
				except MPTimeoutError:
					next_pending.append(async_result)
					continue
				except _TimeUp:
					completed = False
					pool.terminate()
					pool.join()
					return best_choice, best_score, completed

				if score > best_score + 1e-6:
					piece = board.getPiece(*move.start)
					if piece is not None:
						best_score = score
						best_choice = (piece, move)

				if options.use_alpha_beta and best_score >= beta:
					pool.terminate()
					pool.join()
					return best_choice, best_score, True

			pending = next_pending

		pool.close()
		pool.join()
		return best_choice, best_score, completed
	finally:
		if pool is not None:
			try:
				pool.terminate()
				pool.join()
			except Exception:  # noqa: BLE001
				pass
		raise_if_cancelled(cancel_event)


def _alphabeta(
	board: Board,
	depth: int,
	maximizing_color: Color,
	alpha: float,
	beta: float,
	options: MinimaxOptions,
	killer_moves: KillerTable,
	history_table: HistoryTable,
	butterfly_table: ButterflyTable,
	ply: int,
    deadline: Optional[float],
	cancel_event: Optional[Event],
) -> float:
	_check_time(deadline, cancel_event)
	if options.use_endgame_tablebase and _is_endgame(board, options):
		return _solve_endgame(board, maximizing_color, options, deadline, 0, set(), cancel_event)
	winner = board.is_game_over()
	if winner is not None:
		if winner == maximizing_color:
			return _WIN_SCORE + depth
		if winner == _opponent(maximizing_color):
			return -_WIN_SCORE - depth
		return 0.0

	if depth == 0:
		if options.use_quiescence:
			return _quiescence(
				board,
				maximizing_color,
				alpha,
				beta,
				options,
				history_table,
				butterfly_table,
				0,
				deadline,
				cancel_event,
			)
		return evaluate_board(board, maximizing_color)

	moves_map = board.getAllValidMoves(board.turn)
	if not moves_map:
		return evaluate_board(board, maximizing_color)

	alpha_orig = alpha
	beta_orig = beta
	best_move: Optional[Move] = None
	board_hash = board.compute_hash() if options.use_transposition else None
	tt_key = (board_hash, maximizing_color) if board_hash is not None else None
	tt_entry = None

	if options.use_transposition and tt_key is not None:
		tt_entry = _TRANSPOSITION_TABLE.get(tt_key)
		if tt_entry and tt_entry.depth >= depth:
			if tt_entry.flag == Bound.EXACT:
				return tt_entry.score
			if tt_entry.flag == Bound.LOWER:
				alpha = max(alpha, tt_entry.score)
			elif tt_entry.flag == Bound.UPPER:
				beta = min(beta, tt_entry.score)
			if options.use_alpha_beta and alpha >= beta:
				return tt_entry.score

	if options.use_null_move and options.use_alpha_beta and _can_try_null_move(board, options, depth):
		prev_turn = board.turn
		prev_hash = board.zobrist_hash
		board.turn = _opponent(board.turn)
		board.zobrist_hash = prev_hash ^ zobrist_turn_key(prev_turn) ^ zobrist_turn_key(board.turn)
		try:
			null_score = _alphabeta(
				board,
				depth - 1 - options.null_move_reduction,
				maximizing_color,
				alpha,
				beta,
				options,
				killer_moves,
				history_table,
				butterfly_table,
				ply + 1,
				deadline,
				cancel_event,
			)
		finally:
			board.turn = prev_turn
			board.zobrist_hash = prev_hash
		if board.turn == maximizing_color and null_score >= beta:
			return null_score
		if board.turn != maximizing_color and null_score <= alpha:
			return null_score

	ordered_moves = _order_moves(
		moves_map,
		board,
		options,
		tt_entry.best_move if tt_entry else None,
		killer_moves,
		history_table,
		butterfly_table,
		ply,
	)

	if board.turn == maximizing_color:
		value = -math.inf
		for idx, (piece, move) in enumerate(ordered_moves):
			_check_time(deadline, cancel_event)
			undo = board.make_move(piece, move)
			if options.use_butterfly_heuristic and not move.is_capture:
				butterfly_table[_move_key(move)] += 1
			reduced = _lmr_reduction(options, depth, idx, piece, move, board.boardSize)
			try:
				if reduced > 0:
					score = _alphabeta(
						board,
						max(1, depth - 1 - reduced),
						maximizing_color,
						alpha,
						beta,
						options,
						killer_moves,
						history_table,
						butterfly_table,
						ply + 1,
						deadline,
						cancel_event,
					)
					if score > alpha:
						score = _alphabeta(
							board,
							depth - 1,
							maximizing_color,
							alpha,
							beta,
							options,
							killer_moves,
							history_table,
							butterfly_table,
							ply + 1,
							deadline,
							cancel_event,
						)
				else:
					score = _alphabeta(
						board,
						depth - 1,
						maximizing_color,
						alpha,
						beta,
						options,
						killer_moves,
						history_table,
						butterfly_table,
						ply + 1,
						deadline,
						cancel_event,
					)
			finally:
				board.unmake_move(undo)
			if score > value:
				value = score
				best_move = move
			if options.use_alpha_beta:
				alpha = max(alpha, value)
				if alpha >= beta:
					if options.use_move_ordering and options.use_killer_moves and not move.is_capture:
						_register_killer_move(killer_moves, ply, move)
					if options.use_history_heuristic and not move.is_capture:
						history_table[_move_key(move)] += depth * depth
					break
	else:
		value = math.inf
		for idx, (piece, move) in enumerate(ordered_moves):
			_check_time(deadline, cancel_event)
			undo = board.make_move(piece, move)
			if options.use_butterfly_heuristic and not move.is_capture:
				butterfly_table[_move_key(move)] += 1
			reduced = _lmr_reduction(options, depth, idx, piece, move, board.boardSize)
			try:
				if reduced > 0:
					score = _alphabeta(
						board,
						max(1, depth - 1 - reduced),
						maximizing_color,
						alpha,
						beta,
						options,
						killer_moves,
						history_table,
						butterfly_table,
						ply + 1,
						deadline,
						cancel_event,
					)
					if score < beta:
						score = _alphabeta(
							board,
							depth - 1,
							maximizing_color,
							alpha,
							beta,
							options,
							killer_moves,
							history_table,
							butterfly_table,
							ply + 1,
							deadline,
							cancel_event,
						)
				else:
					score = _alphabeta(
						board,
						depth - 1,
						maximizing_color,
						alpha,
						beta,
						options,
						killer_moves,
						history_table,
						butterfly_table,
						ply + 1,
						deadline,
						cancel_event,
					)
			finally:
				board.unmake_move(undo)
			if score < value:
				value = score
				best_move = move
			if options.use_alpha_beta:
				beta = min(beta, value)
				if alpha >= beta:
					if options.use_move_ordering and options.use_killer_moves and not move.is_capture:
						_register_killer_move(killer_moves, ply, move)
					if options.use_history_heuristic and not move.is_capture:
						history_table[_move_key(move)] += depth * depth
					break

	if options.use_transposition and tt_key is not None:
		_store_tt_entry(tt_key, depth, value, alpha_orig, beta_orig, best_move)

	return value


def _quiescence(
	board: Board,
	maximizing_color: Color,
	alpha: float,
	beta: float,
	options: MinimaxOptions,
	history_table: HistoryTable,
	butterfly_table: ButterflyTable,
	depth: int,
    deadline: Optional[float],
	cancel_event: Optional[Event],
) -> float:
	_check_time(deadline, cancel_event)
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

	ordered = _order_moves(
		capture_map,
		board,
		options,
		None,
		defaultdict(list),
		history_table,
		butterfly_table,
		depth,
	)

	if board.turn == maximizing_color:
		value = stand_pat
		for piece, move in ordered:
			_check_time(deadline, cancel_event)
			undo = board.make_move(piece, move)
			try:
				value = max(
					value,
					_quiescence(
						board,
						maximizing_color,
						alpha,
						beta,
						options,
						history_table,
						butterfly_table,
						depth + 1,
						deadline,
						cancel_event,
					),
				)
			finally:
				board.unmake_move(undo)
			if options.use_alpha_beta:
				alpha = max(alpha, value)
				if alpha >= beta:
					break
		return value

	value = stand_pat
	for piece, move in ordered:
		_check_time(deadline, cancel_event)
		undo = board.make_move(piece, move)
		try:
			value = min(
				value,
				_quiescence(
					board,
					maximizing_color,
					alpha,
					beta,
					options,
					history_table,
					butterfly_table,
					depth + 1,
					deadline,
					cancel_event,
				),
			)
		finally:
			board.unmake_move(undo)
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
	history_table: HistoryTable,
	butterfly_table: ButterflyTable,
	ply: int,
) -> List[Tuple[Piece, Move]]:
	pairs = [(piece, move) for piece, moves in moves_map.items() for move in moves]

	prefix: List[Tuple[Piece, Move]] = []
	if tt_move is not None:
		for idx, (_, move) in enumerate(pairs):
			if move == tt_move:
				prefix.append(pairs.pop(idx))
				break

	if not options.use_move_ordering:
		if options.deterministic_ordering:
			pairs.sort(key=lambda pair: _fallback_move_key(pair[1]))
		return prefix + pairs

	scored: List[Tuple[float, Tuple[int, int, int, int, int, int], Tuple[Piece, Move]]] = []
	killers = killer_moves.get(ply, ()) if options.use_killer_moves else ()
	for piece, move in pairs:
		score = _move_sort_score(
			piece,
			move,
			board.boardSize,
			tt_move=None,
			killers=killers,
			history_table=history_table,
			butterfly_table=butterfly_table,
			options=options,
		)
		scored.append((score, _fallback_move_key(move), (piece, move)))

	scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
	return prefix + [pair for _, _, pair in scored]


def _move_sort_score(
	piece: Piece,
	move: Move,
	board_size: int,
	tt_move: Optional[Move],
	killers: Iterable[Move],
	history_table: HistoryTable,
	butterfly_table: ButterflyTable,
	options: MinimaxOptions,
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
	if options.use_history_heuristic and not move.is_capture:
		key = _move_key(move)
		history_value = history_table.get(key, 0)
		if options.use_butterfly_heuristic:
			denominator = max(1, butterfly_table.get(key, 1))
			history_value = history_value / denominator
		score += history_value * 0.01
	return score


def _would_promote(piece: Piece, move: Move, board_size: int) -> bool:
	if piece.is_king:
		return False
	last_row = 0 if piece.color == Color.WHITE else board_size - 1
	return move.end[0] == last_row


def _move_key(move: Move) -> Tuple[int, int, int, int, int]:
	return (*move.start, *move.end, len(move.captures))


def _fallback_move_key(move: Move) -> Tuple[int, int, int, int, int, int]:
	return (
		0 if move.is_capture else 1,
		-len(move.captures),
		move.start[0],
		move.start[1],
		move.end[0],
		move.end[1],
	)


def _can_try_null_move(board: Board, options: MinimaxOptions, depth: int) -> bool:
	if depth <= options.null_move_reduction + 1:
		return False
	if options.use_endgame_tablebase and _is_endgame(board, options):
		return False
	moves_map = board.getAllValidMoves(board.turn)
	if not moves_map:
		return False
	first_moves = next(iter(moves_map.values()), None)
	if first_moves and first_moves[0].is_capture:
		return False
	return True


def _lmr_reduction(
	options: MinimaxOptions,
	depth: int,
	index: int,
	piece: Piece,
	move: Move,
	board_size: int,
) -> int:
	if not options.use_lmr:
		return 0
	if depth < options.lmr_min_depth:
		return 0
	if index < options.lmr_min_moves:
		return 0
	if move.is_capture:
		return 0
	if _would_promote(piece, move, board_size):
		return 0
	return max(1, options.lmr_reduction)


def _is_endgame(board: Board, options: MinimaxOptions) -> bool:
	return len(board.getAllPieces()) <= options.endgame_max_pieces


def _solve_endgame(
	board: Board,
	maximizing_color: Color,
	options: MinimaxOptions,
	deadline: Optional[float],
	ply: int,
	seen: set[Tuple[int, Color]],
	cancel_event: Optional[Event],
) -> float:
	_check_time(deadline, cancel_event)
	winner = board.is_game_over()
	if winner is not None:
		if winner == maximizing_color:
			return _WIN_SCORE - ply
		if winner == _opponent(maximizing_color):
			return -_WIN_SCORE + ply
		return 0.0
	if ply >= options.endgame_max_plies:
		return evaluate_board(board, maximizing_color)
	key = (board.compute_hash(), maximizing_color)
	if key in _ENDGAME_TABLEBASE:
		return _ENDGAME_TABLEBASE[key]
	if key in seen:
		return 0.0
	seen.add(key)

	moves_map = board.getAllValidMoves(board.turn)
	if not moves_map:
		seen.remove(key)
		return 0.0

	ordered = _order_moves(
		moves_map,
		board,
		options,
		tt_move=None,
		killer_moves=defaultdict(list),
		history_table=defaultdict(int),
		butterfly_table=defaultdict(int),
		ply=ply,
	)

	if board.turn == maximizing_color:
		value = -math.inf
		for _, move in ordered:
			_check_time(deadline, cancel_event)
			piece = board.getPiece(*move.start)
			if piece is None:
				continue
			undo = board.make_move(piece, move)
			try:
				value = max(value, _solve_endgame(board, maximizing_color, options, deadline, ply + 1, seen, cancel_event))
			finally:
				board.unmake_move(undo)
	else:
		value = math.inf
		for _, move in ordered:
			_check_time(deadline, cancel_event)
			piece = board.getPiece(*move.start)
			if piece is None:
				continue
			undo = board.make_move(piece, move)
			try:
				value = min(value, _solve_endgame(board, maximizing_color, options, deadline, ply + 1, seen, cancel_event))
			finally:
				board.unmake_move(undo)

	seen.remove(key)
	_ENDGAME_TABLEBASE[key] = value
	return value


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
	key: tuple[int, Color],
	depth: int,
	score: float,
	alpha_orig: float,
	beta_orig: float,
	best_move: Optional[Move],
) -> None:
	if len(_TRANSPOSITION_TABLE) >= _MAX_TT_ENTRIES:
		# Depth-biased eviction among a small window of oldest entries to keep
		# replacements cheap while preferring to retain deeper analysis.
		evict_key = None
		evict_depth = math.inf
		for idx, (existing_key, entry) in enumerate(_TRANSPOSITION_TABLE.items()):
			if idx >= 64:
				break
			if entry.depth < evict_depth:
				evict_depth = entry.depth
				evict_key = existing_key
				if evict_depth <= 0:
					break
		if evict_key is None:
			evict_key = next(iter(_TRANSPOSITION_TABLE))
		_TRANSPOSITION_TABLE.pop(evict_key, None)
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
	history_table: HistoryTable,
	butterfly_table: ButterflyTable,
	alpha: float,
	beta: float,
	deadline: Optional[float],
	cancel_event: Optional[Event],
) -> Tuple[Move, float]:
	piece = board.getPiece(*move.start)
	if piece is None:
		raise ValueError("No piece found at move start when evaluating root move.")
	undo = board.make_move(piece, move)
	try:
		score = _alphabeta(
			board,
			depth,
			maximizing_color,
			alpha,
			beta,
			options,
			defaultdict(list),
			history_table,
			butterfly_table,
			ply=1,
			deadline=deadline,
			cancel_event=cancel_event,
		)
	finally:
		board.unmake_move(undo)
	return move, score


def _alpha_inf() -> float:
	return math.inf


def _check_time(deadline: Optional[float], cancel_event: Optional[Event]) -> None:
	raise_if_cancelled(cancel_event)
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
