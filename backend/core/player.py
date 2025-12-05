from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from .game import Game
    from .move import Move
    from .pieces import Piece

MoveDecision = Tuple["Piece", "Move"]
MovePolicy = Callable[["Game"], Optional[MoveDecision]]


class PlayerKind(str, Enum):
    HUMAN = "human"
    MINIMAX = "minimax"
    MINIMAX_SIMPLE = "minimax_simple"
    MONTE_CARLO = "monte_carlo"
    GENETIC = "genetic"
    REINFORCEMENT = "reinforcement"
    REMOTE = "remote"


@dataclass
class PlayerController:
    kind: PlayerKind
    name: str
    policy: Optional[MovePolicy] = None

    @property
    def is_human(self) -> bool:
        return self.policy is None or self.kind == PlayerKind.HUMAN

    def select_move(self, game: "Game") -> Optional[MoveDecision]:
        if self.policy is None:
            return None
        return self.policy(game)

    @classmethod
    def human(cls, name: str) -> "PlayerController":
        return cls(kind=PlayerKind.HUMAN, name=name)
