from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from ai.huistic import _back_rank_guard, evaluate_board  # noqa: E402
from core.board import Board  # noqa: E402
from core.pieces import Color, Man  # noqa: E402


class HeuristicEvalTests(unittest.TestCase):
    def test_back_rank_guard_uses_home_rank(self) -> None:
        size = 8
        white_home = size - 1
        black_home = 0
        self.assertEqual(_back_rank_guard(Man(Color.WHITE, white_home, 0), size), 1.0)
        self.assertEqual(_back_rank_guard(Man(Color.WHITE, 0, 0), size), 0.0)
        self.assertEqual(_back_rank_guard(Man(Color.BLACK, black_home, 1), size), 1.0)
        self.assertEqual(_back_rank_guard(Man(Color.BLACK, size - 1, 1), size), 0.0)

    def test_eval_is_antisymmetric(self) -> None:
        for size in (8, 10):
            board = Board(size)
            w = evaluate_board(board, Color.WHITE)
            b = evaluate_board(board, Color.BLACK)
            self.assertAlmostEqual(w, -b, places=7)

    def test_threatened_piece_is_penalized(self) -> None:
        # Black can capture the white man on (3,2): (2,1) x (4,3).
        threatened = Board.empty(8, turn=Color.WHITE)
        threatened.board[2][1] = Man(Color.BLACK, 2, 1)
        threatened.board[3][2] = Man(Color.WHITE, 3, 2)
        threatened.zobrist_hash = threatened.recompute_hash()

        # Same material, but move the white man to an edge square that is not immediately capturable.
        safe = Board.empty(8, turn=Color.WHITE)
        safe.board[2][1] = Man(Color.BLACK, 2, 1)
        safe.board[3][0] = Man(Color.WHITE, 3, 0)
        safe.zobrist_hash = safe.recompute_hash()

        self.assertLess(evaluate_board(threatened, Color.WHITE), evaluate_board(safe, Color.WHITE))

