from __future__ import annotations

import math
import random
import os
import multiprocessing as mp
from dataclasses import dataclass, field
from threading import Event
from typing import Iterable, Optional, Tuple

from .huistic import evaluate_board
from .cancel import CancelledError, raise_if_cancelled

from core.board import Board
from core.game import Game
from core.move import Move
from core.pieces import Color, Man, Piece


@dataclass
class MCTSNode:
    parent: Optional["MCTSNode"] = None
    move: Optional[Move] = None
    children: list["MCTSNode"] = field(default_factory=list)
    visits: int = 0
    value: float = 0.0
    untried_moves: Optional[list[Move]] = None
    board_hash: int = 0

    def is_fully_expanded(self) -> bool:
        return self.untried_moves is not None and not self.untried_moves

    def best_child(
        self,
        exploration_constant: float,
        stats: Optional[dict[int, tuple[int, float]]] = None,
    ) -> "MCTSNode":
        parent_visits, _ = _node_stats(self, stats)
        parent_visits = max(1, parent_visits)

        def ucb(child: "MCTSNode") -> float:
            visits, value = _node_stats(child, stats)
            if visits == 0:
                return math.inf
            exploit = value / visits
            explore = exploration_constant * math.sqrt(math.log(parent_visits) / visits)
            return exploit + explore

        return max(self.children, key=ucb)


def _mcts_process_worker(
    root_state,
    root_player: Color,
    worker_iterations: int,
    rollout_depth: int,
    exploration_constant: float,
    seed: Optional[int],
    rollout_policy: str,
    guidance_depth: int,
    rollout_cutoff_depth: Optional[int],
    leaf_evaluation: str,
    use_transposition: bool,
    transposition_max_entries: int,
    progressive_widening: bool,
    pw_k: float,
    pw_alpha: float,
    moves_cache_max_entries: int,
) -> Optional[Move]:
    board = Board.from_state(root_state)
    board.moves_cache_max_entries = min(board.moves_cache_max_entries, moves_cache_max_entries)
    return _search_single(
        board,
        root_player,
        worker_iterations,
        rollout_depth,
        exploration_constant,
        seed,
        rollout_policy,
        guidance_depth,
        rollout_cutoff_depth,
        leaf_evaluation,
        use_transposition,
        transposition_max_entries,
        progressive_widening,
        pw_k,
        pw_alpha,
        None,
    )


def select_move(
    game: Game,
    *,
    iterations: int = 500,
    rollout_depth: int = 80,
    exploration_constant: float = 1.4,
    random_seed: Optional[int] = None,
    use_parallel: bool = False,
    workers: int = 1,
    rollout_policy: str = "random",
    guidance_depth: int = 1,
    rollout_cutoff_depth: Optional[int] = None,
    leaf_evaluation: str = "random_terminal",
    use_transposition: bool = False,
    transposition_max_entries: int = 200_000,
    progressive_widening: bool = False,
    pw_k: float = 1.5,
    pw_alpha: float = 0.5,
    cancel_event: Optional[Event] = None,
) -> Optional[Tuple[Piece, Move]]:
    """Return the best move found by Monte Carlo Tree Search.

    The rollout reward is from the perspective of the root player.
    """
    if iterations <= 0:
        raise ValueError("Iterations must be positive.")
    if rollout_depth <= 0:
        raise ValueError("Rollout depth must be positive.")

    raise_if_cancelled(cancel_event)

    root_board = game.board.copy()
    # Rollouts visit many unique states; keep the move cache bounded to avoid churn.
    root_board.moves_cache_max_entries = min(root_board.moves_cache_max_entries, 2048)
    root_player = root_board.turn
    moves_map = root_board.getAllValidMoves(root_player)
    if not moves_map:
        return None

    if use_parallel and workers > 1:
        stats = _parallel_search(
            root_board,
            root_player,
            iterations,
            rollout_depth,
            exploration_constant,
            random_seed,
            workers,
            rollout_policy,
            guidance_depth,
            rollout_cutoff_depth,
            leaf_evaluation,
            use_transposition,
            transposition_max_entries,
            progressive_widening,
            pw_k,
            pw_alpha,
            cancel_event,
        )
        if not stats:
            return None
        best_move = max(stats.items(), key=lambda item: item[1])[0]
    else:
        best_move = _search_single(
            root_board,
            root_player,
            iterations,
            rollout_depth,
            exploration_constant,
            random_seed,
            rollout_policy,
            guidance_depth,
            rollout_cutoff_depth,
            leaf_evaluation,
            use_transposition,
            transposition_max_entries,
            progressive_widening,
            pw_k,
            pw_alpha,
            cancel_event,
        )

    if best_move is None:
        return None

    piece = game.board.getPiece(*best_move.start)
    if piece is None:
        return None
    return (piece, best_move)


def _search_single(
    root_board: Board,
    root_player: Color,
    iterations: int,
    rollout_depth: int,
    exploration_constant: float,
    random_seed: Optional[int],
    rollout_policy: str,
    guidance_depth: int,
    rollout_cutoff_depth: Optional[int],
    leaf_evaluation: str,
    use_transposition: bool,
    transposition_max_entries: int,
    progressive_widening: bool,
    pw_k: float,
    pw_alpha: float,
    cancel_event: Optional[Event],
) -> Optional[Move]:
    rng = random.Random(random_seed)
    root = MCTSNode(parent=None, move=None, board_hash=root_board.compute_hash())
    stats: Optional[dict[int, tuple[int, float]]] = {} if use_transposition else None
    move_buffer: list[Move] = []
    capture_buffer: list[Move] = []
    promotion_buffer: list[Move] = []
    rollout_undos: list = []

    for _ in range(iterations):
        raise_if_cancelled(cancel_event)
        node = root
        board = root_board
        path_undos: list = []

        try:
            # Selection / Expansion (with optional progressive widening)
            while True:
                raise_if_cancelled(cancel_event)
                _ensure_untried_moves(node, board)
                if node.untried_moves and _can_expand(node, progressive_widening, pw_k, pw_alpha):
                    move = _pop_random_move(node.untried_moves, rng)
                    piece = board.getPiece(*move.start)
                    if piece is None:
                        break
                    undo = board.make_move(piece, move)
                    path_undos.append(undo)

                    child = MCTSNode(parent=node, move=move, board_hash=board.compute_hash())
                    node.children.append(child)
                    node = child
                    break

                if node.children:
                    node = node.best_child(exploration_constant, stats)
                    if node.move is None:
                        break
                    piece = board.getPiece(*node.move.start)
                    if piece is None:
                        break
                    undo = board.make_move(piece, node.move)
                    path_undos.append(undo)
                    continue
                break

            # Simulation
            reward = _rollout(
                board,
                root_player,
                rollout_depth,
                rng,
                rollout_policy,
                guidance_depth,
                rollout_cutoff_depth,
                leaf_evaluation,
                cancel_event,
                move_buffer,
                capture_buffer,
                promotion_buffer,
                rollout_undos,
            )

            # Backpropagation
            current = node
            while current is not None:
                current.visits += 1
                current.value += reward
                if stats is not None:
                    visits, value = stats.get(current.board_hash, (0, 0.0))
                    stats[current.board_hash] = (visits + 1, value + reward)
                    if len(stats) > transposition_max_entries:
                        stats.pop(next(iter(stats)))
                current = current.parent
        finally:
            for undo in reversed(path_undos):
                board.unmake_move(undo)

    if not root.children:
        return None
    best_child = max(root.children, key=lambda child: _node_stats(child, stats)[0] if stats is not None else child.visits)
    return best_child.move


def _node_stats(node: MCTSNode, stats: Optional[dict[int, tuple[int, float]]]) -> tuple[int, float]:
    if stats is None:
        return node.visits, node.value
    return stats.get(node.board_hash, (0, 0.0))


def _can_expand(node: MCTSNode, progressive_widening: bool, pw_k: float, pw_alpha: float) -> bool:
    if not progressive_widening:
        return True
    allowed = max(1, int(pw_k * (max(1, node.visits) ** pw_alpha)))
    return len(node.children) < allowed


def _parallel_search(
    root_board: Board,
    root_player: Color,
    iterations: int,
    rollout_depth: int,
    exploration_constant: float,
    random_seed: Optional[int],
    workers: int,
    rollout_policy: str,
    guidance_depth: int,
    rollout_cutoff_depth: Optional[int],
    leaf_evaluation: str,
    use_transposition: bool,
    transposition_max_entries: int,
    progressive_widening: bool,
    pw_k: float,
    pw_alpha: float,
    cancel_event: Optional[Event],
) -> dict[Move, int]:
    iterations = max(1, iterations)
    cpu_total = os.cpu_count() or 1
    workers = max(1, min(int(workers), iterations, cpu_total))
    base = iterations // workers
    remainder = iterations % workers

    ctx = mp.get_context("spawn")

    root_state = root_board.to_state()

    pool = None
    try:
        pool = ctx.Pool(processes=workers, maxtasksperchild=1)
        args_list = []
        for idx in range(workers):
            worker_iterations = base + (1 if idx < remainder else 0)
            if worker_iterations <= 0:
                worker_iterations = 1
            args_list.append((idx, worker_iterations))

        async_results = []
        for seed_offset, worker_iterations in args_list:
            seed = None if random_seed is None else random_seed + seed_offset
            async_results.append(
                pool.apply_async(
                    _mcts_process_worker,
                    (
                        root_state,
                        root_player,
                        worker_iterations,
                        rollout_depth,
                        exploration_constant,
                        seed,
                        rollout_policy,
                        guidance_depth,
                        rollout_cutoff_depth,
                        leaf_evaluation,
                        use_transposition,
                        transposition_max_entries,
                        progressive_widening,
                        pw_k,
                        pw_alpha,
                        2048,
                    ),
                )
            )
        stats: dict[Move, int] = {}

        pending = list(async_results)
        while pending:
            raise_if_cancelled(cancel_event)

            next_pending = []
            for async_result in pending:
                try:
                    move = async_result.get(timeout=0.05)
                except mp.TimeoutError:
                    next_pending.append(async_result)
                    continue

                if move is not None:
                    stats[move] = stats.get(move, 0) + 1

            pending = next_pending

        pool.close()
        pool.join()
        return stats
    finally:
        if pool is not None:
            try:
                pool.terminate()
                pool.join()
            except Exception:  # noqa: BLE001
                pass
        raise_if_cancelled(cancel_event)


def _rollout(
    board: Board,
    root_player: Color,
    rollout_depth: int,
    rng: random.Random,
    rollout_policy: str,
    guidance_depth: int,
    rollout_cutoff_depth: Optional[int],
    leaf_evaluation: str,
    cancel_event: Optional[Event],
    move_buffer: list[Move],
    capture_buffer: list[Move],
    promotion_buffer: list[Move],
    undo_buffer: list,
) -> float:
    cutoff = rollout_cutoff_depth if rollout_cutoff_depth is not None else rollout_depth

    undo_buffer.clear()
    try:
        for ply in range(rollout_depth):
            raise_if_cancelled(cancel_event)
            moves_map = board.getAllValidMoves(board.turn)
            if not moves_map:
                opponent = _opponent(board.turn)
                if not board.getAllValidMoves(opponent):
                    return 0.0
                return _reward(opponent, root_player)

            if ply >= cutoff:
                return _leaf_value(board, root_player, guidance_depth, leaf_evaluation, cancel_event)

            move = _choose_rollout_move(
                board,
                moves_map,
                rng,
                rollout_policy,
                guidance_depth,
                move_buffer,
                capture_buffer,
                promotion_buffer,
                cancel_event,
            )
            piece = board.getPiece(*move.start)
            if piece is None:
                return 0.0
            undo_buffer.append(board.make_move(piece, move))

        return _leaf_value(board, root_player, guidance_depth, leaf_evaluation, cancel_event)
    finally:
        for undo in reversed(undo_buffer):
            board.unmake_move(undo)


def _choose_rollout_move(
    board: Board,
    moves_map: dict[Piece, Iterable[Move]],
    rng: random.Random,
    rollout_policy: str,
    guidance_depth: int,
    move_buffer: list[Move],
    capture_buffer: list[Move],
    promotion_buffer: list[Move],
    cancel_event: Optional[Event],
) -> Move:
    if rollout_policy == "minimax_guided":
        guided = _choose_guided_move(board, moves_map, guidance_depth, cancel_event)
        if guided is not None:
            return guided
    if rollout_policy == "heuristic":
        guided = _choose_guided_move(board, moves_map, 1, cancel_event)
        if guided is not None:
            return guided

    move_buffer.clear()
    capture_buffer.clear()
    promotion_buffer.clear()

    for moves in moves_map.values():
        for move in moves:
            move_buffer.append(move)
            if move.is_capture:
                capture_buffer.append(move)
            elif _is_promotion_move(board, move):
                promotion_buffer.append(move)

    if capture_buffer:
        return rng.choice(capture_buffer)
    if promotion_buffer:
        return rng.choice(promotion_buffer)
    return rng.choice(move_buffer)


def _choose_guided_move(
    board: Board,
    moves_map: dict[Piece, Iterable[Move]],
    depth: int,
    cancel_event: Optional[Event],
) -> Optional[Move]:
    moves = _collect_moves(moves_map)
    if not moves:
        return None

    current_player = board.turn
    best_move = None
    best_score = -math.inf
    for move in moves:
        raise_if_cancelled(cancel_event)
        piece = board.getPiece(*move.start)
        if piece is None:
            continue
        undo = board.make_move(piece, move)
        try:
            score = _minimax_eval(board, current_player, depth - 1, cancel_event)
        finally:
            board.unmake_move(undo)
        if score > best_score:
            best_score = score
            best_move = move
    return best_move


def _minimax_eval(board: Board, maximizing_color: Color, depth: int, cancel_event: Optional[Event]) -> float:
    winner = board.is_game_over()
    if winner is not None:
        return 1.0 if winner == maximizing_color else -1.0

    if depth <= 0:
        return _normalize_eval(evaluate_board(board, maximizing_color))

    moves_map = board.getAllValidMoves(board.turn)
    if not moves_map:
        return _normalize_eval(evaluate_board(board, maximizing_color))

    if board.turn == maximizing_color:
        value = -math.inf
        for move in _collect_moves(moves_map):
            raise_if_cancelled(cancel_event)
            piece = board.getPiece(*move.start)
            if piece is None:
                continue
            undo = board.make_move(piece, move)
            try:
                value = max(value, _minimax_eval(board, maximizing_color, depth - 1, cancel_event))
            finally:
                board.unmake_move(undo)
        return value

    value = math.inf
    for move in _collect_moves(moves_map):
        raise_if_cancelled(cancel_event)
        piece = board.getPiece(*move.start)
        if piece is None:
            continue
        undo = board.make_move(piece, move)
        try:
            value = min(value, _minimax_eval(board, maximizing_color, depth - 1, cancel_event))
        finally:
            board.unmake_move(undo)
    return value


def _leaf_value(board: Board, root_player: Color, guidance_depth: int, leaf_evaluation: str, cancel_event: Optional[Event]) -> float:
    if leaf_evaluation == "heuristic_eval":
        return _normalize_eval(evaluate_board(board, root_player))
    if leaf_evaluation == "minimax_eval":
        return _minimax_eval(board, root_player, guidance_depth, cancel_event)
    return 0.0


def _normalize_eval(score: float) -> float:
    return max(-1.0, min(1.0, score / 1000.0))


def _collect_moves(moves_map: dict[Piece, Iterable[Move]]) -> list[Move]:
    return [move for moves in moves_map.values() for move in moves]


def _ensure_untried_moves(node: MCTSNode, board: Board) -> None:
    if node.untried_moves is not None:
        return
    moves_map = board.getAllValidMoves(board.turn)
    node.untried_moves = _collect_moves(moves_map)


def _pop_random_move(moves: list[Move], rng: random.Random) -> Move:
    idx = rng.randrange(len(moves))
    moves[idx], moves[-1] = moves[-1], moves[idx]
    return moves.pop()


def _is_promotion_move(board: Board, move: Move) -> bool:
    piece = board.getPiece(*move.start)
    if piece is None or not isinstance(piece, Man):
        return False
    end_row, _ = move.end
    last_row = 0 if piece.color == Color.WHITE else board.boardSize - 1
    return end_row == last_row


def _reward(winner: Color, root_player: Color) -> float:
    if winner == root_player:
        return 1.0
    if winner == _opponent(root_player):
        return -1.0
    return 0.0


def _opponent(color: Color) -> Color:
    return Color.BLACK if color == Color.WHITE else Color.WHITE
