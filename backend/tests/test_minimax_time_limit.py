import sys
import time
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from ai import minimax  # noqa: E402
from core.game import Game  # noqa: E402


class MinimaxTimeLimitTests(unittest.TestCase):
    def test_time_limit_is_ignored_without_iterative_deepening(self) -> None:
        game = Game(board_size=8)
        minimax.clear_transposition_table()

        captured = {"deadline": "unset"}
        original_search_root = minimax._search_root

        def fake_search_root(*args, **kwargs):
            captured["deadline"] = kwargs.get("deadline")
            root_moves = args[2]
            return root_moves[0], 0.0, True

        minimax._search_root = fake_search_root
        try:
            _ = minimax.select_move(
                game,
                depth=12,
                use_iterative_deepening=False,
                time_limit_ms=10,
                use_alpha_beta=True,
                use_transposition=True,
                use_move_ordering=True,
                use_parallel=False,
            )
        finally:
            minimax._search_root = original_search_root

        self.assertIsNone(captured["deadline"])

    def test_iterative_deepening_returns_best_so_far_on_timeout(self) -> None:
        game = Game(board_size=8)
        minimax.clear_transposition_table()
        t0 = time.perf_counter()
        decision = minimax.select_move(
            game,
            depth=12,
            use_iterative_deepening=True,
            time_limit_ms=1,
            use_alpha_beta=True,
            use_transposition=True,
            use_move_ordering=True,
            use_parallel=False,
        )
        dt = time.perf_counter() - t0
        self.assertLess(dt, 1.0)
        self.assertIsNotNone(decision)


if __name__ == "__main__":
    unittest.main()
