from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .board import Board
from .move import Move
from .pieces import Color, Piece
from .player import PlayerController

@dataclass
class MoveRecord:
    piece_before: Piece
    piece_after: Piece
    move: Move
    captured: list[Piece]

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

    def requestAIMove(self) -> bool:
        controller = self.currentController()
        if controller.is_human:
            return False
        decision = controller.select_move(self)
        if decision is None:
            return False
        piece, move = decision
        return self.makeMove(piece, move)
    
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
        captured = self.board.movePiece(piece, move)
        end_row, end_col = move.end
        moved_piece = self.board.getPiece(end_row, end_col)
        if moved_piece is None:
            raise RuntimeError("Moved piece is missing from the board.")
        self.move_history.append(
            MoveRecord(
                piece_before=snapshot,
                piece_after=moved_piece,
                move=move,
                captured=captured.copy(),
            )
        )
        self.winner = self.board.is_game_over()
        self.switchTurn()
        return True

    def simulateMove(self, piece: Piece, move: Move) -> Board:
        if piece not in self.board.getAllPieces():
            raise ValueError("Piece must belong to the current board to simulate a move.")
        if move not in self.getValidMoves().get(piece, []):
            raise ValueError("Move must be valid for the specified piece to simulate it.")
        return self.board.simulateMove(move)
        
    def isGameOver(self):
        res = self.board.is_game_over()
        self.winner = res
        return res
    
    def getWinner(self):
        return self.winner
    
    def undoMove(self):
        if not self.move_history:
            print("No moves to undo.")
            return
        record = self.move_history.pop()
        end_row, end_col = record.move.end
        self.board.board[end_row][end_col] = None
        for cap in record.captured:
            self.board.board[cap.row][cap.col] = cap
        start_row, start_col = record.move.start
        record.piece_before.move(start_row, start_col)
        self.board.board[start_row][start_col] = record.piece_before
        self.board.turn = record.piece_before.color
        self.switchTurn()
        self.winner = None
        
    def displayBoard(self):
        self.board.printBoard()
    
    def runTurn(self):
        if self.isGameOver():
            print(f"Game over! Winner: {self.getWinner().value if self.winner else 'Draw'}")
            return

        controller = self.currentController()
        print(f"{controller.name} ({self.current_player.value}) to move.")
        self.displayBoard()

        moves = self.getValidMoves()
        if not moves:
            print(f"No moves for {self.current_player.value}.")
            self.winner = Color.BLACK if self.current_player == Color.WHITE else Color.WHITE
            return

        if controller.is_human:
            print(f"Available moves for {self.current_player.value}:")
            for i, (piece, options) in enumerate(moves.items(), 1):
                print(f"{i}. {piece}")
                for j, move in enumerate(options, 1):
                    print(f"   {j}: {move}")

            try:
                idx = int(input("Select piece number: ")) - 1
                selected_piece = list(moves.keys())[idx]
                move_idx = int(input(f"Select move number (1-{len(moves[selected_piece])}): ")) - 1
                selected_move = moves[selected_piece][move_idx]
            except (ValueError, IndexError):
                print("Invalid input.")
                return
        else:
            decision = controller.select_move(self)
            if decision is None:
                print(f"{controller.name} cannot find a move.")
                self.winner = Color.BLACK if self.current_player == Color.WHITE else Color.WHITE
                return
            selected_piece, selected_move = decision

        success = self.makeMove(selected_piece, selected_move)
        if success and self.winner:
            print(f"Game Over! Winner: {self.winner.value}")