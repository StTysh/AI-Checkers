from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from threading import Event
from typing import Iterable, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

from .huistic import evaluate_board
from .cancel import CancelledError, raise_if_cancelled

from core.board import Board
from core.game import Game
from core.move import Move
from core.pieces import Color, Man, Piece


@dataclass
class MCTSNode:
    board: Board
    parent: Optional["MCTSNode"] = None
    move: Optional[Move] = None
    children: list["MCTSNode"] = field(default_factory=list)
    visits: int = 0
    value: float = 0.0
    untried_moves: list[Move] = field(default_factory=list)
    board_hash: int = 0

    def __post_init__(self) -> None:
        self.board_hash = self.board.compute_hash()
        if not self.untried_moves:
            moves_map = self.board.getAllValidMoves(self.board.turn)
            self.untried_moves = _collect_moves(moves_map)

    def is_fully_expanded(self) -> bool:
        return not self.untried_moves

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
    root = MCTSNode(board=root_board)
    stats: Optional[dict[int, tuple[int, float]]] = {} if use_transposition else None

    for _ in range(iterations):
        raise_if_cancelled(cancel_event)
        node = root

        # Selection / Expansion (with optional progressive widening)
        while True:
            raise_if_cancelled(cancel_event)
            if node.untried_moves and _can_expand(node, progressive_widening, pw_k, pw_alpha):
                move = rng.choice(node.untried_moves)
                node.untried_moves.remove(move)
                child_board = node.board.simulateMove(move)
                child = MCTSNode(board=child_board, parent=node, move=move)
                node.children.append(child)
                node = child
                break
            if node.children:
                node = node.best_child(exploration_constant, stats)
                continue
            break

        # Simulation
        reward = _rollout(
            node.board,
            root_player,
            rollout_depth,
            rng,
            rollout_policy,
            guidance_depth,
            rollout_cutoff_depth,
            leaf_evaluation,
            cancel_event,
        )

        # Backpropagation
        while node is not None:
            node.visits += 1
            node.value += reward
            if stats is not None:
                visits, value = stats.get(node.board_hash, (0, 0.0))
                stats[node.board_hash] = (visits + 1, value + reward)
                if len(stats) > transposition_max_entries:
                    stats.pop(next(iter(stats)))
            node = node.parent

    if not root.children:
        return None
    if stats is None:
        best_child = max(root.children, key=lambda child: child.visits)
    else:
        best_child = max(root.children, key=lambda child: _node_stats(child, stats)[0])
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
    workers = max(1, min(int(workers), iterations))
    base = iterations // workers
    remainder = iterations % workers

    def _worker(seed_offset: int, worker_iterations: int) -> dict[Move, int]:
        move = _search_single(
            root_board,
            root_player,
            worker_iterations,
            rollout_depth,
            exploration_constant,
            None if random_seed is None else random_seed + seed_offset,
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
        return {move: 1} if move else {}

    stats: dict[Move, int] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        for idx in range(workers):
            worker_iterations = base + (1 if idx < remainder else 0)
            if worker_iterations <= 0:
                worker_iterations = 1
            futures.append(executor.submit(_worker, idx, worker_iterations))
        try:
            for future in futures:
                result = future.result()
                for move, count in result.items():
                    stats[move] = stats.get(move, 0) + count
        except CancelledError:
            for future in futures:
                future.cancel()
            raise
    return stats


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
) -> float:
    current = board

    cutoff = rollout_cutoff_depth if rollout_cutoff_depth is not None else rollout_depth

    for ply in range(rollout_depth):
        raise_if_cancelled(cancel_event)
        winner = current.is_game_over()
        if winner is not None:
            return _reward(winner, root_player)

        if ply >= cutoff:
            return _leaf_value(current, root_player, guidance_depth, leaf_evaluation)

        moves_map = current.getAllValidMoves(current.turn)
        if not moves_map:
            return 0.0

        move = _choose_rollout_move(current, moves_map, rng, rollout_policy, guidance_depth)
        current = current.simulateMove(move)

    return _leaf_value(current, root_player, guidance_depth, leaf_evaluation)


def _choose_rollout_move(
    board: Board,
    moves_map: dict[Piece, Iterable[Move]],
    rng: random.Random,
    rollout_policy: str,
    guidance_depth: int,
) -> Move:
    if rollout_policy == "minimax_guided":
        guided = _choose_guided_move(board, moves_map, guidance_depth)
        if guided is not None:
            return guided
    if rollout_policy == "heuristic":
        guided = _choose_guided_move(board, moves_map, 1)
        if guided is not None:
            return guided

    moves = _collect_moves(moves_map)
    capture_moves = [move for move in moves if move.is_capture]
    if capture_moves:
        return rng.choice(capture_moves)

    promotion_moves = [move for move in moves if _is_promotion_move(board, move)]
    if promotion_moves:
        return rng.choice(promotion_moves)

    return rng.choice(moves)


def _choose_guided_move(
    board: Board,
    moves_map: dict[Piece, Iterable[Move]],
    depth: int,
) -> Optional[Move]:
    moves = _collect_moves(moves_map)
    if not moves:
        return None

    current_player = board.turn
    best_move = None
    best_score = -math.inf
    for move in moves:
        child = board.simulateMove(move)
        score = _minimax_eval(child, current_player, depth - 1)
        if score > best_score:
            best_score = score
            best_move = move
    return best_move


def _minimax_eval(board: Board, maximizing_color: Color, depth: int) -> float:
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
            value = max(value, _minimax_eval(board.simulateMove(move), maximizing_color, depth - 1))
        return value

    value = math.inf
    for move in _collect_moves(moves_map):
        value = min(value, _minimax_eval(board.simulateMove(move), maximizing_color, depth - 1))
    return value


def _leaf_value(board: Board, root_player: Color, guidance_depth: int, leaf_evaluation: str) -> float:
    if leaf_evaluation == "heuristic_eval":
        return _normalize_eval(evaluate_board(board, root_player))
    if leaf_evaluation == "minimax_eval":
        return _minimax_eval(board, root_player, guidance_depth)
    return 0.0


def _normalize_eval(score: float) -> float:
    return max(-1.0, min(1.0, score / 1000.0))


def _collect_moves(moves_map: dict[Piece, Iterable[Move]]) -> list[Move]:
    return [move for moves in moves_map.values() for move in moves]


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
