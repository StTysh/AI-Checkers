from __future__ import annotations

from core.game import Game
from core.player import PlayerController, PlayerKind
from threading import Event
from typing import Optional

from .minimax import select_move as minimax_select
from .mcts import select_move as mcts_select

__all__ = [
    "create_minimax_controller",
    "create_mcts_controller",
]


def create_minimax_controller(
    name: str,
    depth: int = 4,
    *,
    use_alpha_beta: bool = True,
    use_transposition: bool = True,
    use_move_ordering: bool = True,
    use_killer_moves: bool = True,
    use_quiescence: bool = True,
    max_quiescence_depth: int = 6,
    use_aspiration: bool = False,
    aspiration_window: float = 50.0,
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
    endgame_max_pieces: int = 6,
    endgame_max_plies: int = 40,
    use_iterative_deepening: bool = False,
    time_limit_ms: int = 1000,
    use_parallel: bool = False,
    workers: int = 1,
) -> PlayerController:
    depth = max(1, depth)

    def _policy(game: Game, cancel_event: Optional[Event] = None):
        return minimax_select(
            game,
            depth=depth,
            use_alpha_beta=use_alpha_beta,
            use_transposition=use_transposition,
            use_move_ordering=use_move_ordering,
            use_killer_moves=use_killer_moves,
            use_quiescence=use_quiescence,
            max_quiescence_depth=max_quiescence_depth,
            use_aspiration=use_aspiration,
            aspiration_window=aspiration_window,
            use_history_heuristic=use_history_heuristic,
            use_butterfly_heuristic=use_butterfly_heuristic,
            use_null_move=use_null_move,
            null_move_reduction=null_move_reduction,
            use_lmr=use_lmr,
            lmr_min_depth=lmr_min_depth,
            lmr_min_moves=lmr_min_moves,
            lmr_reduction=lmr_reduction,
            deterministic_ordering=deterministic_ordering,
            use_endgame_tablebase=use_endgame_tablebase,
            endgame_max_pieces=endgame_max_pieces,
            endgame_max_plies=endgame_max_plies,
            use_iterative_deepening=use_iterative_deepening,
            time_limit_ms=time_limit_ms,
            use_parallel=use_parallel,
            workers=workers,
            cancel_event=cancel_event,
        )

    flags = []
    if use_alpha_beta:
        flags.append("AB")
    if use_transposition:
        flags.append("TT")
    if use_move_ordering:
        flags.append("MO")
    if use_killer_moves:
        flags.append("KM")
    if use_quiescence:
        flags.append("Q")
    if use_iterative_deepening:
        search = f"id={depth}, {time_limit_ms}ms"
    else:
        search = f"d={depth}"
    parallel = f", p={workers}" if use_parallel else ""
    suffix = f" ({search}{parallel}{', ' + '/'.join(flags) if flags else ''})"

    return PlayerController(
        kind=PlayerKind.MINIMAX,
        name=f"{name} Minimax{suffix}",
        policy=_policy,
    )


def create_mcts_controller(
    name: str,
    *,
    iterations: int = 500,
    rollout_depth: int = 80,
    exploration_constant: float = 1.4,
    random_seed: int | None = None,
    use_parallel: bool = False,
    workers: int = 1,
    rollout_policy: str = "random",
    guidance_depth: int = 1,
    rollout_cutoff_depth: int | None = None,
    leaf_evaluation: str = "random_terminal",
    use_transposition: bool = False,
    transposition_max_entries: int = 200_000,
    progressive_widening: bool = False,
    pw_k: float = 1.5,
    pw_alpha: float = 0.5,
    progressive_bias: bool = False,
    pb_weight: float = 0.0,
) -> PlayerController:
    iterations = max(1, iterations)
    rollout_depth = max(1, rollout_depth)
    exploration_constant = max(0.01, exploration_constant)

    def _policy(game: Game, cancel_event: Optional[Event] = None):
        return mcts_select(
            game,
            iterations=iterations,
            rollout_depth=rollout_depth,
            exploration_constant=exploration_constant,
            random_seed=random_seed,
            use_parallel=use_parallel,
            workers=workers,
            rollout_policy=rollout_policy,
            guidance_depth=guidance_depth,
            rollout_cutoff_depth=rollout_cutoff_depth,
            leaf_evaluation=leaf_evaluation,
            use_transposition=use_transposition,
            transposition_max_entries=transposition_max_entries,
            progressive_widening=progressive_widening,
            pw_k=pw_k,
            pw_alpha=pw_alpha,
            progressive_bias=progressive_bias,
            pb_weight=pb_weight,
            cancel_event=cancel_event,
        )

    suffix = f" (iter={iterations}, depth={rollout_depth}, C={exploration_constant:.2f})"
    if use_parallel:
        suffix += f", p={workers}"
    if rollout_policy != "random":
        suffix += f", policy={rollout_policy}"
    if rollout_cutoff_depth:
        suffix += f", cutoff={rollout_cutoff_depth}"
    if leaf_evaluation != "random_terminal":
        suffix += f", leaf={leaf_evaluation}"
    if progressive_bias:
        suffix += f", pb={pb_weight:.2f}"
    if random_seed is not None:
        suffix += f", seed={random_seed}"

    return PlayerController(
        kind=PlayerKind.MONTE_CARLO,
        name=f"{name} MCTS{suffix}",
        policy=_policy,
    )
