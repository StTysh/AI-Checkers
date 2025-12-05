from __future__ import annotations

from core.game import Game
from core.player import PlayerController, PlayerKind

from .minimax import select_move as minimax_select
from .simple_minimax import select_move as simple_minimax_select

__all__ = ["create_minimax_controller", "create_simple_minimax_controller"]


def create_minimax_controller(
    name: str,
    depth: int = 4,
    *,
    use_transposition: bool = True,
    use_move_ordering: bool = True,
    use_quiescence: bool = True,
) -> PlayerController:
    depth = max(1, depth)

    def _policy(game: Game):
        return minimax_select(
            game,
            depth=depth,
            use_transposition=use_transposition,
            use_move_ordering=use_move_ordering,
            use_quiescence=use_quiescence,
        )

    flags = []
    if use_transposition:
        flags.append("TT")
    if use_move_ordering:
        flags.append("MO")
    if use_quiescence:
        flags.append("Q")
    suffix = f" (d={depth}{', ' + '/'.join(flags) if flags else ''})"

    return PlayerController(
        kind=PlayerKind.MINIMAX,
        name=f"{name} Minimax{suffix}",
        policy=_policy,
    )


def create_simple_minimax_controller(name: str, depth: int = 4) -> PlayerController:
    depth = max(1, depth)

    def _policy(game: Game):
        return simple_minimax_select(game, depth=depth)

    return PlayerController(
        kind=PlayerKind.MINIMAX_SIMPLE,
        name=f"{name} Minimax (baseline d={depth})",
        policy=_policy,
    )
