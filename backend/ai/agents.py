from __future__ import annotations

from core.game import Game
from core.player import PlayerController, PlayerKind

from .minimax import select_move as minimax_select

__all__ = ["create_minimax_controller"]


def create_minimax_controller(name: str, depth: int = 4) -> PlayerController:
    depth = max(1, depth)

    def _policy(game: Game):
        return minimax_select(game, depth=depth)

    return PlayerController(
        kind=PlayerKind.MINIMAX,
        name=f"{name} (d={depth})",
        policy=_policy,
    )
