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


class MoveCacheAndOrderingTests(unittest.TestCase):
    def test_moves_cache_is_identity_safe(self) -> None:
        """Cache is keyed by Zobrist (layout-only), so cached values must not depend on piece identity."""

        board = Board.empty(8, turn=Color.WHITE)
        a = Man(Color.WHITE, 5, 0, identifier=1)
        b = Man(Color.WHITE, 5, 2, identifier=2)
        board.board[5][0] = a
        board.board[5][2] = b
        board.zobrist_hash = board.recompute_hash()
        board.use_move_cache = True
        board._moves_cache.clear()

        moves1 = board.getAllValidMoves(Color.WHITE)
        self.assertTrue(moves1)

        # Swap identities while keeping the same layout (Zobrist hash stays the same).
        board.board[5][0] = b
        b.move(5, 0)
        board.board[5][2] = a
        a.move(5, 2)
        swapped_hash = board.recompute_hash()
        self.assertEqual(swapped_hash, board.zobrist_hash)

        moves2 = board.getAllValidMoves(Color.WHITE)
        self.assertTrue(moves2)

        for piece, moves in moves2.items():
            for move in moves:
                self.assertEqual(move.start, (piece.row, piece.col))

    def test_minimax_orders_tt_best_move_first(self) -> None:
        board = Board(8)
        moves_map = board.getAllValidMoves(board.turn)
        self.assertTrue(moves_map)

        piece = next(iter(moves_map.keys()))
        tt_move = moves_map[piece][0]

        options = minimax.MinimaxOptions(use_move_ordering=True, deterministic_ordering=True)
        ordered = list(
            minimax._order_moves(
                moves_map,
                board,
                options,
                tt_move=tt_move,
                killer_moves=defaultdict(list),
                history_table=defaultdict(int),
                butterfly_table=defaultdict(int),
                ply=0,
            )
        )
        self.assertTrue(ordered)
        self.assertEqual(ordered[0][1], tt_move)


if __name__ == "__main__":
    unittest.main()
