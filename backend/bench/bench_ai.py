from __future__ import annotations

import math
import sys
import time
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ai.huistic import evaluate_board  # noqa: E402
from ai import minimax, mcts  # noqa: E402
from core.board import Board  # noqa: E402
from core.game import Game  # noqa: E402
from core.move import Move  # noqa: E402
from core.pieces import Piece  # noqa: E402


def _flatten_moves(moves_map: dict[Piece, list[Move]]) -> list[tuple[Piece, Move]]:
    return [(piece, move) for piece, moves in moves_map.items() for move in moves]


def bench_moves_cache(board_size: int, loops: int = 20000) -> None:
    board = Board(board_size)

    def run(enabled: bool) -> float:
        board.use_move_cache = enabled
        board._moves_cache.clear()
        start = time.perf_counter()
        for _ in range(loops):
            _ = board.getAllValidMoves(board.turn)
        return time.perf_counter() - start

    cached = run(True)
    uncached = run(False)
    print(f"[moves cache ON ] size={board_size} loops={loops}  {cached:.4f}s")
    print(f"[moves cache OFF] size={board_size} loops={loops}  {uncached:.4f}s  (x{uncached / max(1e-9, cached):.2f} slower)")


def bench_apply_vs_copy(board_size: int, loops: int = 5000) -> None:
    board = Board(board_size)
    pairs = _flatten_moves(board.getAllValidMoves(board.turn))
    pairs = pairs[: max(1, min(len(pairs), 32))]

    start = time.perf_counter()
    for i in range(loops):
        piece, move = pairs[i % len(pairs)]
        undo = board.make_move(piece, move)
        board.unmake_move(undo)
    inplace = time.perf_counter() - start

    start = time.perf_counter()
    for i in range(loops):
        _, move = pairs[i % len(pairs)]
        _ = board.simulateMove(move)
    copy_style = time.perf_counter() - start

    print(f"[apply/unapply] size={board_size} loops={loops}  {inplace:.4f}s")
    print(f"[simulate/copy ] size={board_size} loops={loops}  {copy_style:.4f}s  (x{copy_style / max(1e-9, inplace):.2f} slower)")


def minimax_baseline_copy(game: Game, depth: int) -> Move | None:
    board = game.board
    moves_map = board.getAllValidMoves(board.turn)
    pairs = _flatten_moves(moves_map)
    if not pairs:
        return None

    maximizing = board.turn

    def negamax(b: Board, d: int, alpha: float, beta: float) -> float:
        winner = b.is_game_over()
        if winner is not None:
            if winner == maximizing:
                return 1_000_000.0 + d
            if winner != maximizing:
                return -1_000_000.0 - d
        if d <= 0:
            return evaluate_board(b, maximizing)
        moves = _flatten_moves(b.getAllValidMoves(b.turn))
        if not moves:
            return evaluate_board(b, maximizing)
        value = -math.inf
        for _, mv in moves:
            child = b.simulateMove(mv)
            score = -negamax(child, d - 1, -beta, -alpha)
            if score > value:
                value = score
            alpha = max(alpha, score)
            if alpha >= beta:
                break
        return value

    best_score = -math.inf
    best = None
    for _, mv in pairs:
        child = board.simulateMove(mv)
        score = -negamax(child, depth - 1, -math.inf, math.inf)
        if score > best_score:
            best_score = score
            best = mv
    return best


def bench_minimax(depth: int = 6) -> None:
    workers = min(4, os.cpu_count() or 1)

    def run_optimized(
        *,
        cache: bool,
        parallel: bool,
        iterative: bool,
        depth_override: int | None = None,
    ) -> float:
        game = Game(board_size=8)
        game.board.use_move_cache = cache
        minimax.clear_transposition_table()
        run_depth = depth if depth_override is None else depth_override
        t0 = time.perf_counter()
        _ = minimax.select_move(
            game,
            depth=run_depth,
            use_alpha_beta=True,
            use_transposition=True,
            use_move_ordering=True,
            use_iterative_deepening=iterative,
            time_limit_ms=60_000 if iterative else 0,
            use_parallel=parallel,
            workers=workers,
        )
        return time.perf_counter() - t0

    def run_baseline(*, cache: bool) -> float:
        game = Game(board_size=8)
        game.board.use_move_cache = cache
        t0 = time.perf_counter()
        _ = minimax_baseline_copy(game, depth=depth)
        return time.perf_counter() - t0

    t_opt_cache = run_optimized(cache=True, parallel=False, iterative=False)
    t_opt_cache_parallel = run_optimized(cache=True, parallel=True, iterative=False)
    t_opt_nocache = run_optimized(cache=False, parallel=False, iterative=False)
    t_base_cache = run_baseline(cache=True)

    print(f"[minimax optimized] depth={depth} cache=on  {t_opt_cache:.4f}s")
    speedup = t_opt_cache / max(1e-9, t_opt_cache_parallel)
    print(f"[minimax optimized] depth={depth} cache=on  parallel({workers}) {t_opt_cache_parallel:.4f}s  (x{speedup:.2f} speedup vs single)")
    print(f"[minimax optimized] depth={depth} cache=off {t_opt_nocache:.4f}s  (x{t_opt_nocache / max(1e-9, t_opt_cache):.2f} slower)")
    print(f"[minimax baseline ] depth={depth} cache=on  {t_base_cache:.4f}s  (x{t_base_cache / max(1e-9, t_opt_cache):.2f} slower vs optimized)")
    t_opt_id = run_optimized(cache=True, parallel=False, iterative=True)
    t_opt_id_parallel = run_optimized(cache=True, parallel=True, iterative=True)
    id_speedup = t_opt_id / max(1e-9, t_opt_id_parallel)
    print(f"[minimax ID     ] depth={depth} cache=on  {t_opt_id:.4f}s")
    print(f"[minimax ID     ] depth={depth} cache=on  parallel({workers}) {t_opt_id_parallel:.4f}s  (x{id_speedup:.2f} speedup vs single)")

    if depth < 8:
        deep = 8
        t_deep_single = run_optimized(cache=True, parallel=False, iterative=False, depth_override=deep)
        t_deep_parallel = run_optimized(cache=True, parallel=True, iterative=False, depth_override=deep)
        deep_speedup = t_deep_single / max(1e-9, t_deep_parallel)
        print(f"[minimax optimized] depth={deep} cache=on  {t_deep_single:.4f}s")
        print(f"[minimax optimized] depth={deep} cache=on  parallel({workers}) {t_deep_parallel:.4f}s  (x{deep_speedup:.2f} speedup vs single)")


def bench_mcts(iterations: int = 2000) -> None:
    workers = min(4, os.cpu_count() or 1)

    def run(*, cache: bool, parallel: bool) -> float:
        game = Game(board_size=8)
        game.board.use_move_cache = cache
        t0 = time.perf_counter()
        _ = mcts.select_move(game, iterations=iterations, rollout_depth=80, use_parallel=parallel, workers=workers)
        return time.perf_counter() - t0

    dt_cache = run(cache=True, parallel=False)
    dt_cache_parallel = run(cache=True, parallel=True)
    dt_nocache = run(cache=False, parallel=False)
    print(f"[mcts optimized] iterations={iterations} cache=on  {dt_cache:.4f}s")
    print(f"[mcts optimized] iterations={iterations} cache=on  parallel({workers}) {dt_cache_parallel:.4f}s  (x{dt_cache / max(1e-9, dt_cache_parallel):.2f} faster)")
    print(f"[mcts optimized] iterations={iterations} cache=off {dt_nocache:.4f}s  (x{dt_nocache / max(1e-9, dt_cache):.2f} slower)")


def main() -> None:
    print("== Microbench: getAllValidMoves cache ==")
    bench_moves_cache(8, loops=20000)
    bench_moves_cache(10, loops=20000)
    print()
    print("== Microbench: apply/unapply vs simulateMove ==")
    bench_apply_vs_copy(8, loops=5000)
    bench_apply_vs_copy(10, loops=5000)
    print()
    print("== Minimax bench ==")
    bench_minimax(depth=6)
    print()
    print("== MCTS bench ==")
    bench_mcts(iterations=5000)


if __name__ == "__main__":
    main()
