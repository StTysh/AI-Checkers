from __future__ import annotations

import math
import sys
import unittest
from collections import defaultdict
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from ai import minimax  # noqa: E402
from core.board import Board  # noqa: E402
from core.pieces import Color, Man  # noqa: E402


class InternationalMajorityCaptureTests(unittest.TestCase):
    def test_international_majority_capture_prefers_longest_sequence(self) -> None:
        board = Board(10)
        board.board = [[None for _ in range(10)] for _ in range(10)]
        board.turn = Color.WHITE

        white = Man(Color.WHITE, 6, 1)
        board.board[6][1] = white

        board.board[5][2] = Man(Color.BLACK, 5, 2)
        board.board[3][4] = Man(Color.BLACK, 3, 4)
        board.board[7][2] = Man(Color.BLACK, 7, 2)

        moves = board.getAllValidMoves(Color.WHITE)[white]
        self.assertTrue(moves)
        self.assertTrue(all(len(move.captures) == 2 for move in moves), moves)


class MinimaxTranspositionPerspectiveTests(unittest.TestCase):
    def test_tt_key_includes_perspective(self) -> None:
        minimax.clear_transposition_table()

        board = Board(8)
        moves_map = board.getAllValidMoves(Color.WHITE)
        first_piece, first_moves = next(iter(moves_map.items()))
        self.assertTrue(first_moves)
        move = first_moves[0]
        board = board.simulateMove(move)

        options = minimax.MinimaxOptions(use_transposition=True, use_alpha_beta=True)
        score_white = minimax._alphabeta(
            board,
            depth=1,
            maximizing_color=Color.WHITE,
            alpha=-math.inf,
            beta=math.inf,
            options=options,
            killer_moves=defaultdict(list),
            history_table=defaultdict(int),
            butterfly_table=defaultdict(int),
            ply=0,
            deadline=None,
            cancel_event=None,
        )
        score_black = minimax._alphabeta(
            board,
            depth=1,
            maximizing_color=Color.BLACK,
            alpha=-math.inf,
            beta=math.inf,
            options=options,
            killer_moves=defaultdict(list),
            history_table=defaultdict(int),
            butterfly_table=defaultdict(int),
            ply=0,
            deadline=None,
            cancel_event=None,
        )

        h = board.compute_hash()
        self.assertIn((h, Color.WHITE), minimax._TRANSPOSITION_TABLE)
        self.assertIn((h, Color.BLACK), minimax._TRANSPOSITION_TABLE)
        self.assertNotEqual(
            minimax._TRANSPOSITION_TABLE[(h, Color.WHITE)].key,
            minimax._TRANSPOSITION_TABLE[(h, Color.BLACK)].key,
        )
        self.assertAlmostEqual(score_white, -score_black, places=6)


if __name__ == "__main__":
    unittest.main()
