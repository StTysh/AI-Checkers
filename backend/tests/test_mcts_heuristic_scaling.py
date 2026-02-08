from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from ai import mcts  # noqa: E402
from core.board import Board  # noqa: E402
from core.pieces import Color, Man  # noqa: E402


class MCTSHeuristicScalingTests(unittest.TestCase):
    def test_heuristic_eval_is_not_near_zero(self) -> None:
        board = Board.empty(8, turn=Color.WHITE)
        board.board[5][0] = Man(Color.WHITE, 5, 0)
        board.board[5][2] = Man(Color.WHITE, 5, 2)
        board.board[2][1] = Man(Color.BLACK, 2, 1)
        board.zobrist_hash = board.recompute_hash()

        value = mcts._leaf_value(board, Color.WHITE, 1, "heuristic_eval", None)
        self.assertGreater(value, 0.05)
        self.assertLess(value, 0.95)

    def test_scaling_is_board_size_dependent(self) -> None:
        # With the same raw score, 10x10 normalization is intentionally "softer".
        self.assertGreater(abs(mcts._normalize_eval(1.0, 8)), abs(mcts._normalize_eval(1.0, 10)))
