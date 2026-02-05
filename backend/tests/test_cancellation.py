from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from ai.cancel import CancelledError  # noqa: E402
from ai import mcts, minimax  # noqa: E402
from core.game import Game  # noqa: E402


class CancellationTests(unittest.TestCase):
    def test_mcts_cancels_immediately(self) -> None:
        event = threading.Event()
        event.set()
        with self.assertRaises(CancelledError):
            mcts.select_move(Game(8), iterations=10_000, cancel_event=event)

    def test_mcts_cancels_mid_search(self) -> None:
        event = threading.Event()
        outcome: list[BaseException] = []

        def worker() -> None:
            try:
                mcts.select_move(
                    Game(8),
                    iterations=1_000_000_000,
                    rollout_depth=300,
                    use_parallel=True,
                    workers=4,
                    cancel_event=event,
                )
            except BaseException as exc:  # noqa: BLE001
                outcome.append(exc)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        time.sleep(0.02)
        event.set()
        thread.join(timeout=2.0)
        self.assertFalse(thread.is_alive(), "MCTS worker did not stop after cancellation.")
        self.assertTrue(outcome, "MCTS worker did not raise an exception on cancellation.")
        self.assertIsInstance(outcome[0], CancelledError)

    def test_minimax_cancels_immediately(self) -> None:
        event = threading.Event()
        event.set()
        with self.assertRaises(CancelledError):
            minimax.select_move(Game(8), depth=6, use_iterative_deepening=True, cancel_event=event)


if __name__ == "__main__":
    unittest.main()

