from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from core.board import Board  # noqa: E402
from core.pieces import Color, King, Man  # noqa: E402


def snapshot(board: Board) -> tuple:
    pieces = []
    for r in range(board.boardSize):
        for c in range(board.boardSize):
            piece = board.getPiece(r, c)
            if piece is None:
                continue
            pieces.append((piece.id, r, c, piece.color.value, piece.is_king, piece.__class__.__name__))
    pieces.sort()
    return (board.boardSize, board.turn.value, tuple(pieces))


class MakeUnmakeTests(unittest.TestCase):
    def test_make_unmake_random_moves_british(self) -> None:
        rng = random.Random(123)
        board = Board(8)
        for _ in range(50):
            before = snapshot(board)
            before_hash = board.compute_hash()
            self.assertEqual(before_hash, board.recompute_hash())

            moves_map = board.getAllValidMoves(board.turn)
            self.assertTrue(moves_map)
            piece = rng.choice(list(moves_map.keys()))
            move = rng.choice(list(moves_map[piece]))

            undo = board.make_move(piece, move)
            self.assertEqual(board.compute_hash(), board.recompute_hash())
            board.unmake_move(undo)

            self.assertEqual(snapshot(board), before)
            self.assertEqual(board.compute_hash(), before_hash)
            self.assertEqual(board.compute_hash(), board.recompute_hash())

    def test_make_unmake_random_moves_international(self) -> None:
        rng = random.Random(456)
        board = Board(10)
        for _ in range(50):
            before = snapshot(board)
            before_hash = board.compute_hash()
            self.assertEqual(before_hash, board.recompute_hash())

            moves_map = board.getAllValidMoves(board.turn)
            self.assertTrue(moves_map)
            piece = rng.choice(list(moves_map.keys()))
            move = rng.choice(list(moves_map[piece]))

            undo = board.make_move(piece, move)
            self.assertEqual(board.compute_hash(), board.recompute_hash())
            board.unmake_move(undo)

            self.assertEqual(snapshot(board), before)
            self.assertEqual(board.compute_hash(), before_hash)
            self.assertEqual(board.compute_hash(), board.recompute_hash())

    def test_make_unmake_multi_jump_british_man(self) -> None:
        board = Board.empty(8, turn=Color.WHITE)
        board.board[5][0] = Man(Color.WHITE, 5, 0)
        board.board[4][1] = Man(Color.BLACK, 4, 1)
        board.board[2][3] = Man(Color.BLACK, 2, 3)
        board.zobrist_hash = board.recompute_hash()

        moves_map = board.getAllValidMoves(Color.WHITE)
        self.assertEqual(len(moves_map), 1)
        piece, moves = next(iter(moves_map.items()))
        move = next((m for m in moves if m.is_capture and len(m.steps) == 2), None)
        self.assertIsNotNone(move)

        before = snapshot(board)
        before_hash = board.compute_hash()
        undo = board.make_move(piece, move)  # type: ignore[arg-type]
        self.assertEqual(board.compute_hash(), board.recompute_hash())
        board.unmake_move(undo)
        self.assertEqual(snapshot(board), before)
        self.assertEqual(board.compute_hash(), before_hash)

    def test_make_unmake_multi_jump_international_king_flying(self) -> None:
        board = Board.empty(10, turn=Color.WHITE)
        board.board[5][4] = King(Color.WHITE, 5, 4)
        board.board[4][3] = Man(Color.BLACK, 4, 3)
        board.board[2][1] = Man(Color.BLACK, 2, 1)
        board.zobrist_hash = board.recompute_hash()

        moves_map = board.getAllValidMoves(Color.WHITE)
        self.assertEqual(len(moves_map), 1)
        piece, moves = next(iter(moves_map.items()))
        move = next((m for m in moves if m.is_capture and len(m.steps) == 2), None)
        self.assertIsNotNone(move)

        before = snapshot(board)
        before_hash = board.compute_hash()
        undo = board.make_move(piece, move)  # type: ignore[arg-type]
        self.assertEqual(board.compute_hash(), board.recompute_hash())
        board.unmake_move(undo)
        self.assertEqual(snapshot(board), before)
        self.assertEqual(board.compute_hash(), before_hash)

    def test_make_unmake_promotion_british(self) -> None:
        board = Board.empty(8, turn=Color.WHITE)
        board.board[1][2] = Man(Color.WHITE, 1, 2)
        board.zobrist_hash = board.recompute_hash()

        moves_map = board.getAllValidMoves(Color.WHITE)
        piece, moves = next(iter(moves_map.items()))
        move = next((m for m in moves if not m.is_capture and m.end[0] == 0), None)
        self.assertIsNotNone(move)

        undo = board.make_move(piece, move)  # type: ignore[arg-type]
        promoted = board.getPiece(*move.end)  # type: ignore[union-attr]
        self.assertIsNotNone(promoted)
        self.assertTrue(promoted.is_king)
        board.unmake_move(undo)
        restored = board.getPiece(1, 2)
        self.assertIsNotNone(restored)
        self.assertFalse(restored.is_king)


if __name__ == "__main__":
    unittest.main()

