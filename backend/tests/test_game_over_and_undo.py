from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from core.board import Board  # noqa: E402
from core.game import Game  # noqa: E402
from core.pieces import Color, Man  # noqa: E402


class BoardGameOverTests(unittest.TestCase):
    def test_game_over_when_side_has_no_pieces(self) -> None:
        board = Board.empty(8, turn=Color.WHITE)
        board.board[5][0] = Man(Color.WHITE, 5, 0)
        board.zobrist_hash = board.recompute_hash()
        self.assertEqual(board.is_game_over(), Color.WHITE)

        board.turn = Color.BLACK
        board.zobrist_hash = board.recompute_hash()
        self.assertEqual(board.is_game_over(), Color.WHITE)

    def test_game_over_when_side_to_move_has_no_moves(self) -> None:
        board = Board.empty(8, turn=Color.WHITE)
        board.board[0][1] = Man(Color.WHITE, 0, 1)
        board.board[7][0] = Man(Color.BLACK, 7, 0)
        board.zobrist_hash = board.recompute_hash()

        self.assertEqual(board.is_game_over(), Color.BLACK)

        board.turn = Color.BLACK
        board.zobrist_hash = board.recompute_hash()
        self.assertEqual(board.is_game_over(), Color.WHITE)


class GameUndoTests(unittest.TestCase):
    def test_undo_restores_state_and_hash(self) -> None:
        game = Game(8)
        before_state = game.board.to_state()
        before_player = game.current_player

        moves_map = game.getValidMoves()
        piece, moves = next(iter(moves_map.items()))
        move = moves[0]
        self.assertTrue(game.makeMove(piece, move))
        game.undoMove()

        self.assertEqual(game.board.to_state(), before_state)
        self.assertEqual(game.current_player, before_player)
        self.assertIsNone(game.winner)
        self.assertEqual(game.board.zobrist_hash, game.board.recompute_hash())

    def test_undo_reverts_promotion(self) -> None:
        game = Game(8)
        board = Board.empty(8, turn=Color.WHITE)

        man = Man(Color.WHITE, 1, 2)
        board.board[1][2] = man
        board.zobrist_hash = board.recompute_hash()

        game.board = board
        game.current_player = board.turn
        game.winner = None
        game.move_history.clear()

        moves_map = game.getValidMoves()
        moves = moves_map[man]
        move = next(m for m in moves if m.end[0] == 0)
        self.assertTrue(game.makeMove(man, move))
        promoted = game.board.getPiece(*move.end)
        self.assertIsNotNone(promoted)
        self.assertTrue(promoted.is_king)

        game.undoMove()
        restored = game.board.getPiece(1, 2)
        self.assertIsNotNone(restored)
        self.assertFalse(restored.is_king)
        self.assertEqual(restored.color, Color.WHITE)
        self.assertEqual(game.board.zobrist_hash, game.board.recompute_hash())


if __name__ == "__main__":
    unittest.main()
