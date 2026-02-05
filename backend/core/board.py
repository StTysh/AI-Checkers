from __future__ import annotations

from typing import Optional

from .move import Move
from .pieces import Piece, Color, Man
from .hash import compute_board_hash


MoveMap = dict[Piece, list[Move]]


class Board:
    def __init__(self, boardSize: int = 8) -> None:
        self.board: list[list[Optional[Piece]]] = [
            [None for _ in range(boardSize)] for _ in range(boardSize)
        ]
        self.boardSize = boardSize
        self.turn = Color.WHITE
        self._set_start_pieces()
    
    def getPiece(self, row: int, col: int) -> Optional[Piece]:
        if self._is_within_bounds(row, col):
            return self.board[row][col]
        return None

    def getAllPieces(self) -> list[Piece]:
        pieces: list[Piece] = []
        for row in range(self.boardSize):
            for col in range(self.boardSize):                
                if (row + col) % 2 == 1:
                    piece = self.getPiece(row, col)
                    if piece:
                        pieces.append(piece)
        return pieces   

    def getAllValidMoves(self, color: Color) -> MoveMap:
        capture_map: MoveMap = {}
        quiet_map: MoveMap = {}

        for piece in self.getAllPieces():
            if piece.color != color:
                continue
            moves = piece.possibleMoves(self)
            if not moves:
                continue

            capture_moves = [move for move in moves if move.is_capture]
            if capture_moves:
                capture_map[piece] = capture_moves
            else:
                quiet_map[piece] = moves


        if not capture_map:
            return quiet_map

        if self.boardSize != 8:
            capture_map = self._filter_majority_captures(capture_map)

        return capture_map

    def _filter_majority_captures(self, capture_map: MoveMap) -> MoveMap:
        """International draughts: enforce majority capture.

        Keep only capture moves that capture the most pieces. If tied, prefer moves
        that capture the most kings.
        """
        all_moves = [move for moves in capture_map.values() for move in moves]
        if not all_moves:
            return capture_map

        max_captures = max(len(move.captures) for move in all_moves)
        by_capture_count: MoveMap = {}
        for piece, moves in capture_map.items():
            filtered = [move for move in moves if len(move.captures) == max_captures]
            if filtered:
                by_capture_count[piece] = filtered
        if not by_capture_count:
            return capture_map

        def kings_captured(move: Move) -> int:
            total = 0
            for row, col in move.captures:
                captured = self.getPiece(row, col)
                if captured is not None and captured.is_king:
                    total += 1
            return total

        max_kings = max(kings_captured(move) for moves in by_capture_count.values() for move in moves)
        majority: MoveMap = {}
        for piece, moves in by_capture_count.items():
            filtered = [move for move in moves if kings_captured(move) == max_kings]
            if filtered:
                majority[piece] = filtered
        return majority if majority else by_capture_count


    def movePiece(self, piece: Piece, move: Move) -> list[Piece]:
        if not move.steps:
            raise ValueError("Move must contain at least one destination step.")
        if move.start != (piece.row, piece.col):
            raise ValueError("Move start does not match piece position.")

        if self.getPiece(piece.row, piece.col) is not piece:
            raise ValueError("Piece must occupy its recorded position before moving.")

        old_row, old_col = piece.row, piece.col
        captured_pieces: list[Piece] = []

        for new_row, new_col in move.steps:
            if not self._is_within_bounds(new_row, new_col):
                raise ValueError("Move path steps must stay within the board.")
            occupant = self.getPiece(new_row, new_col)
            if occupant and occupant is not piece:
                raise ValueError("Destination square must be empty.")
            self.board[old_row][old_col] = None
            self.board[new_row][new_col] = piece
            piece.move(new_row, new_col)

            step_captures = self._handle_captures(piece, old_row, old_col, new_row, new_col)
            if step_captures:
                captured_pieces.extend(step_captures)

            old_row, old_col = new_row, new_col

        if move.is_capture and not captured_pieces:
            raise RuntimeError("Capture move resulted in no captures.")
        if move.is_capture and len(captured_pieces) != len(move.captures):
            raise RuntimeError("Capture move capture count mismatch.")
        if move.is_capture:
            actual_coords = tuple((p.row, p.col) for p in captured_pieces)
            if actual_coords != move.captures:
                raise RuntimeError("Capture move capture sequence mismatch.")
        if not move.is_capture and captured_pieces:
            raise RuntimeError("Quiet move unexpectedly captured pieces.")

        promoted = self._handle_promotion(piece)
        if promoted is not piece:
            piece = promoted  

        self.turn = Color.BLACK if self.turn == Color.WHITE else Color.WHITE
        return captured_pieces
    
    def copy(self) -> "Board":
        new_board = Board(self.boardSize)
        new_board.board = [[None for _ in range(self.boardSize)] for _ in range(self.boardSize)]
        new_board.turn = self.turn
        for r in range(self.boardSize):
            for c in range(self.boardSize):
                p = self.getPiece(r, c)
                if p:
                    new_board.board[r][c] = p.getCopy()
        return new_board

    def simulateMove(self, move: Move) -> "Board":
        board_copy = self.copy()
        piece = board_copy.getPiece(*move.start)
        if piece is None:
            raise ValueError("No piece found at move start when simulating move.")
        board_copy.movePiece(piece, move)
        return board_copy

    def compute_hash(self) -> int:
        return compute_board_hash(self)

    def _remove_piece(self, piece: Piece):
        if piece and self.getPiece(piece.row, piece.col) == piece:
            self.board[piece.row][piece.col] = None

    def _handle_captures(
        self,
        piece: Piece,
        old_row: int,
        old_col: int,
        new_row: int,
        new_col: int,
    ) -> list[Piece]:
        captured: list[Piece] = []

        if self.boardSize == 8:
            if abs(new_row - old_row) == 2:
                mid_row = (old_row + new_row) // 2
                mid_col = (old_col + new_col) // 2
                mid_piece = self.getPiece(mid_row, mid_col)
                if mid_piece and mid_piece.color != piece.color:
                    self._remove_piece(mid_piece)
                    captured.append(mid_piece)
        else:  
            dr = 1 if new_row > old_row else -1
            dc = 1 if new_col > old_col else -1
            r, c = old_row + dr, old_col + dc
            while r != new_row and c != new_col:
                mid_piece = self.getPiece(r, c)
                if mid_piece and mid_piece.color != piece.color:
                    self._remove_piece(mid_piece)
                    captured.append(mid_piece)
                    break
                r += dr
                c += dc

        return captured
    

    def _handle_promotion(self, piece: Piece) -> Piece:
        if isinstance(piece, Man):
            last_row = 0 if piece.color == Color.WHITE else self.boardSize - 1
            if piece.row == last_row:
                promoted = piece.promote()
                self.board[piece.row][piece.col] = promoted
                return promoted
        return piece             
    
    def _set_start_pieces(self):
        rows_to_fill = 3 if self.boardSize == 8 else 4

        for row in range(self.boardSize):
            for col in range(self.boardSize):
                
                if (row + col) % 2 == 1:
                    if row < rows_to_fill:
                        self.board[row][col] = Man(Color.BLACK, row, col)
                    elif row >= self.boardSize - rows_to_fill:
                        self.board[row][col] = Man(Color.WHITE, row, col)

    def _is_within_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.boardSize and 0 <= col < self.boardSize
    
    def is_game_over(self) -> Optional[Color]:
        white_moves = self.getAllValidMoves(Color.WHITE)
        black_moves = self.getAllValidMoves(Color.BLACK)
        if not white_moves and not black_moves:
            return None  
        if not white_moves:
            return Color.BLACK
        if not black_moves:
            return Color.WHITE
        return None





#|       |  **0**  |  **1**  |  **2**  |  **3**  |  **4**  |  **5**  |  **6**  |  **7**  |
#| ----- |---------|---------|---------|---------|---------|---------|---------|---------|
#|       |         |	     |         |         |         |         |         |         |
#| **0** | [0] [0] | [0] [1] | [0] [2] | [0] [3] | [0] [4] | [0] [5] | [0] [6] | [0] [7] |
#|	     |	       |	     |         |         |         |         |         |         |
#| ----- |---------|---------|---------|---------|---------|---------|---------|---------|
#|	     |	       |	     |         |         |         |         |         |         |
#| **1** | [1] [0] | [1] [1] | [1] [2] | [1] [3] | [1] [4] | [1] [5] | [1] [6] | [1] [7] |
#|	     |	       |	     |         |         |         |         |         |         |
#| ----- |---------|---------|---------|---------|---------|---------|---------|---------|
#|	     |	       |	     |         |         |         |         |         |         |
#| **2** | [2] [0] | [2] [1] | [2] [2] | [2] [3] | [2] [4] | [2] [5] | [2] [6] | [2] [7] |
#|	     |	       |	     |         |         |         |         |         |         |
#| ----- |---------|---------|---------|---------|---------|---------|---------|---------|
#|	     |	       |	     |         |         |         |         |         |         |
#| **3** | [3] [0] | [3] [1] | [3] [2] | [3] [3] | [3] [4] | [3] [5] | [3] [6] | [3] [7] |
#|	     |	       |	     |         |         |         |         |         |         |
#| ----- |---------|---------|---------|---------|---------|---------|---------|---------|
#|	     |	       |	     |         |         |         |         |         |         |
#| **4** | [4] [0] | [4] [1] | [4] [2] | [4] [3] | [4] [4] | [4] [5] | [4] [6] | [4] [7] |
#|	     |	       |	     |         |         |         |         |         |         |
#| ----- |---------|---------|---------|---------|---------|---------|---------|---------|
#|	     |	       |	     |         |         |         |         |         |         |
#| **5** | [5] [0] | [5] [1] | [5] [2] | [5] [3] | [5] [4] | [5] [5] | [5] [6] | [5] [7] |
#|	     |	       |	     |         |         |         |         |         |         |
#| ----- |---------|---------|---------|---------|---------|---------|---------|---------|
#|	     |	       |	     |         |         |         |         |         |         |
#| **6** | [6] [0] | [6] [1] | [6] [2] | [6] [3] | [6] [4] | [6] [5] | [6] [6] | [6] [7] |
#|	     |	       |	     |         |         |         |         |         |         |
#| ----- |---------|---------|---------|---------|---------|---------|---------|---------|
#|	     |	       |	     |         |         |         |         |         |         |
#| **7** | [7] [0] | [7] [1] | [7] [2] | [7] [3] | [7] [4] | [7] [5] | [7] [6] | [7] [7] |
#|	     |	       |	     |         |         |         |         |         |         |
#| ----- |---------|---------|---------|---------|---------|---------|---------|---------|
