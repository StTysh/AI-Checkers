from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Optional


@dataclass(frozen=True, slots=True)
class CancelledError(RuntimeError):
    message: str = "AI computation canceled."

    def __str__(self) -> str:  # pragma: no cover
        return self.message


def raise_if_cancelled(cancel_event: Optional[Event]) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise CancelledError()

