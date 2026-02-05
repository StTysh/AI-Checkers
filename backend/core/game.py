from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .board import Board, UndoRecord
from .move import Move
from .pieces import Color, Piece
from .player import PlayerController

@dataclass
class MoveRecord:
    piece_before: Piece
    piece_after: Piece
    move: Move
    captured: list[Piece]
    undo: Optional[UndoRecord] = None

class Game:
    """Core game wrapper that can run on different board sizes."""

    def __init__(self, board_size: int = 8):
        self.board_size = board_size
        self.board = Board(board_size)
        self.current_player = self.board.turn
        self.winner: Optional[Color] = None
        self.move_history: list[MoveRecord] = []
        self.players: dict[Color, PlayerController] = {
            Color.WHITE: PlayerController.human("White Human"),
            Color.BLACK: PlayerController.human("Black Human"),
        }

    def reset(self, board_size: Optional[int] = None):
        if board_size is not None:
            self.board_size = board_size
        self.board = Board(self.board_size)
        self.current_player = self.board.turn
        self.winner = None
        self.move_history.clear()
        # Lazy import avoids a circular dependency during module load time.
        from ai.minimax import clear_transposition_table

        clear_transposition_table()

    def switchTurn(self):
        self.current_player = self.board.turn
        

    def getValidMoves(self) -> dict[Piece, list[Move]]:
        return self.board.getAllValidMoves(self.current_player)

    def setPlayer(self, color: Color, controller: PlayerController) -> None:
        self.players[color] = controller

    def getPlayer(self, color: Color) -> PlayerController:
        return self.players[color]

    def currentController(self) -> PlayerController:
        return self.getPlayer(self.current_player)

    def isAITurn(self) -> bool:
        return not self.currentController().is_human
    
    def makeMove(self, piece: Piece, move: Move) -> bool:
        if not piece or move is None:
            return False
        valid_moves = self.getValidMoves()
        if piece not in valid_moves:
            print("Invalid piece selection.")
            return False
        if move not in valid_moves[piece]:
            print("Invalid move selection.")
            return False
        snapshot = piece.getCopy()
        undo = self.board.make_move(piece, move)
        captured = list(undo.captured)
        end_row, end_col = undo.end
        moved_piece = self.board.getPiece(end_row, end_col)
        if moved_piece is None:
            raise RuntimeError("Moved piece is missing from the board.")
        self.move_history.append(
            MoveRecord(
                piece_before=snapshot,
                piece_after=moved_piece,
                move=move,
                captured=captured.copy(),
                undo=undo,
            )
        )
        self.winner = self.board.is_game_over()
        self.switchTurn()
        return True

    
    def undoMove(self):
        if not self.move_history:
            print("No moves to undo.")
            return
        record = self.move_history.pop()
        if record.undo is not None:
            self.board.unmake_move(record.undo)
        else:
            end_row, end_col = record.move.end
            self.board.board[end_row][end_col] = None
            for cap in record.captured:
                self.board.board[cap.row][cap.col] = cap
            start_row, start_col = record.move.start
            record.piece_before.move(start_row, start_col)
            self.board.board[start_row][start_col] = record.piece_before
            self.board.turn = record.piece_before.color
            self.board.zobrist_hash = self.board.recompute_hash()
            self.board._moves_cache.clear()
        self.switchTurn()
        self.winner = None
        
