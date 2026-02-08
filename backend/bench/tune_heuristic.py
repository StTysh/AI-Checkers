from __future__ import annotations

import argparse
import contextlib
import dataclasses
import math
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import ai.huistic as huistic  # noqa: E402
from ai import minimax  # noqa: E402
from core.game import Game  # noqa: E402
from core.pieces import Color  # noqa: E402


@dataclass(frozen=True)
class MinimaxConfig:
    depth: int
    iterative_deepening: bool
    time_limit_ms: int
    alpha_beta: bool
    transposition: bool
    move_ordering: bool
    killer_moves: bool
    quiescence: bool
    max_quiescence_depth: int
    aspiration: bool
    aspiration_window: float
    null_move: bool
    null_move_reduction: int
    lmr: bool
    lmr_min_depth: int
    lmr_min_moves: int
    lmr_reduction: int
    deterministic_ordering: bool


@dataclass(frozen=True)
class MatchSummary:
    games: int
    wins: int
    draws: int
    losses: int
    score: float
    avg_plies: float
    avg_seconds: float


def _profile_dict(profile: huistic.EvalProfile) -> dict[str, float]:
    return {field.name: float(getattr(profile, field.name)) for field in dataclasses.fields(huistic.EvalProfile)}


def _profile_from_dict(values: dict[str, float]) -> huistic.EvalProfile:
    return huistic.EvalProfile(**values)


def _format_profile_python(name: str, profile: huistic.EvalProfile) -> str:
    values = _profile_dict(profile)
    lines = [f"{name} = EvalProfile("]
    for field in dataclasses.fields(huistic.EvalProfile):
        val = values[field.name]
        lines.append(f"    {field.name}={val:.6g},")
    lines.append(")")
    return "\n".join(lines)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _mutate_profile(
    base: huistic.EvalProfile,
    rng: random.Random,
    *,
    sigma: float,
    weight_max: float,
    king_min: float,
    king_max: float,
    freeze: set[str],
) -> huistic.EvalProfile:
    values = _profile_dict(base)

    def mutate_field(field_name: str, *, lo: float, hi: float) -> None:
        if field_name in freeze:
            return
        original = values[field_name]
        if original <= 0.0:
            original = 1e-6
        factor = math.exp(rng.gauss(0.0, sigma))
        values[field_name] = _clamp(original * factor, lo, hi)

    # Keep material baseline stable unless explicitly allowed.
    if "man_value" not in freeze:
        values["man_value"] = 1.0

    mutate_field("king_value_open", lo=king_min, hi=king_max)
    mutate_field("king_value_end", lo=king_min, hi=king_max)
    values["king_value_end"] = max(values["king_value_end"], values["king_value_open"])

    for field in dataclasses.fields(huistic.EvalProfile):
        if field.name in ("man_value", "king_value_open", "king_value_end"):
            continue
        mutate_field(field.name, lo=0.0, hi=weight_max)

    return _profile_from_dict(values)


@contextlib.contextmanager
def _use_profile(board_size: int, profile: huistic.EvalProfile):
    if board_size == 8:
        old = huistic._PROFILE_8
        huistic._PROFILE_8 = profile
        try:
            yield
        finally:
            huistic._PROFILE_8 = old
        return

    old = huistic._PROFILE_10
    huistic._PROFILE_10 = profile
    try:
        yield
    finally:
        huistic._PROFILE_10 = old


@contextlib.contextmanager
def _use_transposition_table(tt: dict):
    old = minimax._TRANSPOSITION_TABLE
    minimax._TRANSPOSITION_TABLE = tt
    try:
        yield
    finally:
        minimax._TRANSPOSITION_TABLE = old


def _pick_random_opening(game: Game, rng: random.Random, plies: int) -> None:
    for _ in range(max(0, plies)):
        winner = game.board.is_game_over()
        if winner is not None:
            game.winner = winner
            return
        moves_map = game.board.getAllValidMoves(game.current_player)
        moves = [move for options in moves_map.values() for move in options]
        if not moves:
            return
        move = rng.choice(moves)
        piece = game.board.getPiece(*move.start)
        if piece is None:
            return
        game.makeMove(piece, move)


def _minimax_move(game: Game, cfg: MinimaxConfig, *, board_size: int, profile: huistic.EvalProfile, tt: dict):
    with _use_profile(board_size, profile), _use_transposition_table(tt):
        decision = minimax.select_move(
            game,
            depth=cfg.depth,
            use_iterative_deepening=cfg.iterative_deepening,
            time_limit_ms=cfg.time_limit_ms,
            use_alpha_beta=cfg.alpha_beta,
            use_transposition=cfg.transposition,
            use_move_ordering=cfg.move_ordering,
            use_killer_moves=cfg.killer_moves,
            use_quiescence=cfg.quiescence,
            max_quiescence_depth=cfg.max_quiescence_depth,
            use_aspiration=cfg.aspiration,
            aspiration_window=cfg.aspiration_window,
            use_null_move=cfg.null_move,
            null_move_reduction=cfg.null_move_reduction,
            use_lmr=cfg.lmr,
            lmr_min_depth=cfg.lmr_min_depth,
            lmr_min_moves=cfg.lmr_min_moves,
            lmr_reduction=cfg.lmr_reduction,
            deterministic_ordering=cfg.deterministic_ordering,
            use_parallel=False,
            workers=1,
            use_endgame_tablebase=False,
        )
    return decision


def _play_game(
    *,
    board_size: int,
    cfg: MinimaxConfig,
    candidate: huistic.EvalProfile,
    baseline: huistic.EvalProfile,
    candidate_color: Color,
    opening_seed: int,
    randomize_plies: int,
    move_cap: int,
) -> tuple[Optional[Color], int, float]:
    game = Game(board_size=board_size)
    opening_rng = random.Random(opening_seed)
    _pick_random_opening(game, opening_rng, randomize_plies)

    tt_candidate: dict = {}
    tt_baseline: dict = {}
    start = time.perf_counter()

    for _ in range(move_cap):
        winner = game.board.is_game_over()
        if winner is not None:
            game.winner = winner
            break

        current = game.current_player
        profile = candidate if current == candidate_color else baseline
        tt = tt_candidate if current == candidate_color else tt_baseline
        decision = _minimax_move(game, cfg, board_size=board_size, profile=profile, tt=tt)
        if decision is None:
            game.winner = Color.BLACK if current == Color.WHITE else Color.WHITE
            break

        piece, move = decision
        if not game.makeMove(piece, move):
            game.winner = Color.BLACK if current == Color.WHITE else Color.WHITE
            break

    elapsed = time.perf_counter() - start
    return game.winner, len(game.move_history), elapsed


def _evaluate(
    *,
    board_size: int,
    cfg: MinimaxConfig,
    candidate: huistic.EvalProfile,
    baseline: huistic.EvalProfile,
    games: int,
    randomize_plies: int,
    move_cap: int,
    base_seed: int,
) -> MatchSummary:
    wins = draws = losses = 0
    total_plies = 0
    total_seconds = 0.0

    for index in range(games):
        candidate_color = Color.WHITE if index % 2 == 0 else Color.BLACK
        winner, plies, seconds = _play_game(
            board_size=board_size,
            cfg=cfg,
            candidate=candidate,
            baseline=baseline,
            candidate_color=candidate_color,
            opening_seed=base_seed + index,
            randomize_plies=randomize_plies,
            move_cap=move_cap,
        )
        total_plies += plies
        total_seconds += seconds

        if winner is None:
            draws += 1
        elif winner == candidate_color:
            wins += 1
        else:
            losses += 1

    score = wins + 0.5 * draws
    avg_plies = total_plies / max(1, games)
    avg_seconds = total_seconds / max(1, games)
    return MatchSummary(
        games=games,
        wins=wins,
        draws=draws,
        losses=losses,
        score=score,
        avg_plies=avg_plies,
        avg_seconds=avg_seconds,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Empirically tune EvalProfile weights via self-play matches.")
    parser.add_argument("--board-size", type=int, choices=(8, 10), default=8)
    parser.add_argument("--depth", type=int, default=6)
    parser.add_argument("--iterative-deepening", action="store_true")
    parser.add_argument("--time-limit-ms", type=int, default=1000)
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--randomize-plies", type=int, default=4)
    parser.add_argument("--move-cap", type=int, default=200)
    parser.add_argument("--trials", type=int, default=60)
    parser.add_argument("--sigma", type=float, default=0.18, help="Mutation strength (log-normal sigma).")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--weight-max", type=float, default=2.0)
    parser.add_argument("--king-min", type=float, default=1.5)
    parser.add_argument("--king-max", type=float, default=6.0)
    parser.add_argument(
        "--freeze",
        type=str,
        default="man_value",
        help="Comma-separated EvalProfile fields to keep fixed (default: man_value).",
    )
    parser.add_argument("--print-best", action="store_true", help="Print best profile as Python snippet.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    rng = random.Random(args.seed)
    freeze = {item.strip() for item in (args.freeze or "").split(",") if item.strip()}

    base_profile = huistic._profile_for(args.board_size)
    best_profile = base_profile

    cfg = MinimaxConfig(
        depth=max(1, int(args.depth)),
        iterative_deepening=bool(args.iterative_deepening),
        time_limit_ms=max(0, int(args.time_limit_ms)) if args.iterative_deepening else 0,
        alpha_beta=True,
        transposition=True,
        move_ordering=True,
        killer_moves=True,
        quiescence=True,
        max_quiescence_depth=6,
        aspiration=False,
        aspiration_window=50.0,
        null_move=False,
        null_move_reduction=2,
        lmr=False,
        lmr_min_depth=3,
        lmr_min_moves=4,
        lmr_reduction=1,
        deterministic_ordering=True,
    )

    print(f"== Heuristic tuner == size={args.board_size} depth={cfg.depth} games={args.games} trials={args.trials}")
    time_note = f"{cfg.time_limit_ms}" if cfg.iterative_deepening else "ignored (iterativeDeepening=OFF)"
    print(f"iterativeDeepening={cfg.iterative_deepening} timeLimitMs={time_note} randomizePlies={args.randomize_plies}")
    print(f"mutation sigma={args.sigma} weightMax={args.weight_max} king=[{args.king_min},{args.king_max}] freeze={sorted(freeze)}")
    print()

    baseline_eval = _evaluate(
        board_size=args.board_size,
        cfg=cfg,
        candidate=best_profile,
        baseline=best_profile,
        games=args.games,
        randomize_plies=args.randomize_plies,
        move_cap=args.move_cap,
        base_seed=args.seed,
    )
    print(f"[baseline self-play] W/D/L={baseline_eval.wins}/{baseline_eval.draws}/{baseline_eval.losses} avgPlies={baseline_eval.avg_plies:.1f} avgSeconds={baseline_eval.avg_seconds:.2f}")

    best_score = -math.inf
    best_summary: MatchSummary | None = None

    for trial in range(1, args.trials + 1):
        candidate = _mutate_profile(
            best_profile,
            rng,
            sigma=float(args.sigma),
            weight_max=float(args.weight_max),
            king_min=float(args.king_min),
            king_max=float(args.king_max),
            freeze=freeze,
        )
        summary = _evaluate(
            board_size=args.board_size,
            cfg=cfg,
            candidate=candidate,
            baseline=best_profile,
            games=args.games,
            randomize_plies=args.randomize_plies,
            move_cap=args.move_cap,
            base_seed=args.seed,
        )
        improved = summary.score > best_score + 1e-9
        if improved:
            best_score = summary.score
            best_profile = candidate
            best_summary = summary

        tag = "BEST" if improved else "    "
        print(f"[{tag}] trial={trial:03d} score={summary.score:.1f}/{args.games} W/D/L={summary.wins}/{summary.draws}/{summary.losses} avgSeconds={summary.avg_seconds:.2f}")

    if best_summary is None:
        print("\nNo improvement found (try more trials/games or higher sigma).")
        return

    print("\n== Best found ==")
    print(f"score={best_summary.score:.1f}/{args.games} W/D/L={best_summary.wins}/{best_summary.draws}/{best_summary.losses} avgSeconds={best_summary.avg_seconds:.2f}")
    if args.print_best:
        profile_name = "_PROFILE_8" if args.board_size == 8 else "_PROFILE_10"
        print("\n" + _format_profile_python(profile_name, best_profile))


if __name__ == "__main__":
    main()
