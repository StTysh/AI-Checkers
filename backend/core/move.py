from __future__ import annotations

from dataclasses import dataclass

Coordinate = tuple[int, int]
MoveSequence = tuple[Coordinate, ...]
CaptureSequence = tuple[Coordinate, ...]


@dataclass(frozen=True, slots=True)
class Move:
    start: Coordinate
    steps: MoveSequence
    captures: CaptureSequence = ()

    @property
    def end(self) -> Coordinate:
        return self.steps[-1] if self.steps else self.start

    @property
    def is_capture(self) -> bool:
        return bool(self.captures)

    def as_path(self) -> tuple[Coordinate, ...]:
        return (self.start, *self.steps)

    def __str__(self) -> str:
        connector = " x " if self.is_capture else " - "
        path = [f"{self.start[0]},{self.start[1]}"] + [f"{row},{col}" for row, col in self.steps]
        return connector.join(path)
