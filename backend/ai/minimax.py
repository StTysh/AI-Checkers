from __future__ import annotations

import math
import os
import time
import logging
from collections import defaultdict
from dataclasses import dataclass, replace
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from enum import Enum, auto
from threading import Event
from typing import DefaultDict, Dict, Iterable, List, Optional, Tuple

from core.board import Board
from core.game import Game
from core.move import Move
from core.pieces import Color, Piece

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
	if use_iterative_deepening and time_limit_ms > 0:
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
						use_parallel=use_parallel,
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
			history_table,
			butterfly_table,
			alpha=-math.inf,
			beta=math.inf,
			use_parallel=use_parallel,
			workers=workers,
			deadline=None,
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
	best_choice: Optional[Tuple[Piece, Move]] = None

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
		_check_time(deadline, cancel_event)
		projected = board.simulateMove(move)
		score = _alphabeta(
			projected,
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
	worker_count = _clamp_workers(workers)
	best_score = -math.inf
	best_choice: Optional[Tuple[Piece, Move]] = None
	completed = True

	# Process pools are fragile/heavy inside a Windows web server (spawn + uvicorn reload +
	# threadpool execution of sync endpoints). Use threads here and disable global TT/endgame
	# tablebase usage per worker to avoid races.
	worker_options = replace(options, use_transposition=False, use_endgame_tablebase=False)

	with ThreadPoolExecutor(max_workers=worker_count) as executor:
		futures = []
		for _, move in root_moves:
			futures.append(
				executor.submit(
					_evaluate_root_move,
					board,
					move,
					depth - 1,
					player,
					worker_options,
					defaultdict(int, history_table),
					defaultdict(int, butterfly_table),
					alpha,
					beta,
					deadline,
					cancel_event,
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
			except CancelledError:
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

		if cancel_event is not None and cancel_event.is_set():
			raise CancelledError()

	return best_choice, best_score, completed


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
		null_board = board.copy()
		null_board.turn = _opponent(board.turn)
		null_score = _alphabeta(
			null_board,
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
			child = board.simulateMove(move)
			if options.use_butterfly_heuristic and not move.is_capture:
				butterfly_table[_move_key(move)] += 1
			reduced = _lmr_reduction(options, depth, idx, piece, move, board.boardSize)
			if reduced > 0:
				score = _alphabeta(
					child,
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
						child,
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
					child,
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
			child = board.simulateMove(move)
			if options.use_butterfly_heuristic and not move.is_capture:
				butterfly_table[_move_key(move)] += 1
			reduced = _lmr_reduction(options, depth, idx, piece, move, board.boardSize)
			if reduced > 0:
				score = _alphabeta(
					child,
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
						child,
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
					child,
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
			child = board.simulateMove(move)
			value = max(
				value,
				_quiescence(
					child,
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
			if options.use_alpha_beta:
				alpha = max(alpha, value)
				if alpha >= beta:
					break
		return value

	value = stand_pat
	for piece, move in ordered:
		_check_time(deadline, cancel_event)
		child = board.simulateMove(move)
		value = min(
			value,
			_quiescence(
				child,
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
	if not options.use_move_ordering:
		ordered = [(piece, move) for piece, moves in moves_map.items() for move in moves]
		if options.deterministic_ordering:
			ordered.sort(key=lambda pair: _fallback_move_key(pair[1]))
		return ordered

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
				history_table,
				butterfly_table,
				options,
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
			child = board.simulateMove(move)
			value = max(value, _solve_endgame(child, maximizing_color, options, deadline, ply + 1, seen, cancel_event))
	else:
		value = math.inf
		for _, move in ordered:
			_check_time(deadline, cancel_event)
			child = board.simulateMove(move)
			value = min(value, _solve_endgame(child, maximizing_color, options, deadline, ply + 1, seen, cancel_event))

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
	history_table: HistoryTable,
	butterfly_table: ButterflyTable,
	alpha: float,
	beta: float,
	deadline: Optional[float],
	cancel_event: Optional[Event],
) -> Tuple[Move, float]:
	projected = board.simulateMove(move)
	score = _alphabeta(
		projected,
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
