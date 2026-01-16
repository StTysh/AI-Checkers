from __future__ import annotations

from core.game import Game
from core.player import PlayerController, PlayerKind

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
    use_iterative_deepening: bool = False,
    time_limit_ms: int = 1000,
    use_parallel: bool = False,
    workers: int = 1,
) -> PlayerController:
    depth = max(1, depth)

    def _policy(game: Game):
        return minimax_select(
            game,
            depth=depth,
            use_alpha_beta=use_alpha_beta,
            use_transposition=use_transposition,
            use_move_ordering=use_move_ordering,
            use_killer_moves=use_killer_moves,
            use_quiescence=use_quiescence,
            max_quiescence_depth=max_quiescence_depth,
            use_iterative_deepening=use_iterative_deepening,
            time_limit_ms=time_limit_ms,
            use_parallel=use_parallel,
            workers=workers,
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
) -> PlayerController:
    iterations = max(1, iterations)
    rollout_depth = max(1, rollout_depth)
    exploration_constant = max(0.01, exploration_constant)

    def _policy(game: Game):
        return mcts_select(
            game,
            iterations=iterations,
            rollout_depth=rollout_depth,
            exploration_constant=exploration_constant,
            random_seed=random_seed,
        )

    suffix = f" (iter={iterations}, depth={rollout_depth}, C={exploration_constant:.2f})"
    if random_seed is not None:
        suffix += f", seed={random_seed}"

    return PlayerController(
        kind=PlayerKind.MONTE_CARLO,
        name=f"{name} MCTS{suffix}",
        policy=_policy,
    )
