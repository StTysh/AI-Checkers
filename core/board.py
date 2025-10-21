from pieces import Piece, Color, Man, King
from typing import Optional



class Board: 
    def __init__(self, boardSize: int = 8) -> None:
        self.board = [[None for _ in range(boardSize)] for _ in range(boardSize)]
        self.boardSize = boardSize
        self.turn = Color.WHITE
        self._set_start_pieces()
    
    def printBoard(self):
        for row in range(self.boardSize):
            line = ""
            for col in range(self.boardSize):
                p = self.board[row][col]
                if not p:
                    line += ". "
                else:
                    if p.color == Color.WHITE:
                        line += "w" if not p.is_king else "W"
                    else:
                        line += "b" if not p.is_king else "B"
                    line += " "
            print(line)
        print()

    def getPiece(self, row: int, col: int) -> Optional[Piece]:
        if(self._is_within_bounds(row,col)):
            return self.board[row] [col]
        else: return None 

    def getAllPieces(self) -> list[Piece] :
        pieces = []
        for row in range(self.boardSize):
            for col in range(self.boardSize):                
                if (row + col) % 2 == 1:
                    piece = self.getPiece(row, col)
                    if(piece): pieces.append(piece)
        return pieces   

    def getAllValidMoves(self, color: Color) -> dict[Piece, list[list[tuple[int, int]]]]:
        capture_map: dict[Piece, list[list[tuple[int, int]]]] = {}
        quiet_map: dict[Piece, list[list[tuple[int, int]]]] = {}

        for piece in self.getAllPieces():
            if piece.color != color:
                continue
            moves = piece.possibleMoves(self)  
            if not moves:
                continue

            
            caps = [p for p in moves if self._path_has_capture(p)]
            if caps:
                capture_map[piece] = caps
            else:
                quiet_map[piece] = moves


        return capture_map if capture_map else quiet_map


    def movePiece(self, piece: Piece, path: list[tuple[int, int]]) -> list[Piece]:
        if not path:
            return []

        old_row, old_col = piece.row, piece.col
        captured_pieces = []

        for (new_row, new_col) in path:
            self.board[old_row] [old_col] = None
            self.board[new_row] [new_col] = piece
            piece.move(new_row, new_col)

            step_captures = self._handle_captures(piece, old_row, old_col, new_row, new_col)
            if step_captures:
                captured_pieces.extend(step_captures)

            old_row, old_col = new_row, new_col

        promoted = self._handle_promotion(piece)
        if promoted is not piece:
            piece = promoted  

        self.turn = Color.BLACK if self.turn == Color.WHITE else Color.WHITE
        return captured_pieces
    
    def copy(self):
        new_board = Board(self.boardSize)
        new_board.board = [[None for _ in range(self.boardSize)] for _ in range(self.boardSize)]
        new_board.turn = self.turn
        for r in range(self.boardSize):
            for c in range(self.boardSize):
                p = self.getPiece(r, c)
                if p:
                    new_board.board[r] [c] = p.getCopy()
        return new_board

    def _remove_piece(self, piece: Piece):
        if(piece and self.getPiece(piece.row,piece.col) == piece):
            self.board[piece.row] [piece.col] = None

    def _handle_captures(self, piece: Piece, old_row, old_col, new_row, new_col) -> list[Piece]:
        captured = []

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
                self.board[piece.row] [piece.col] = promoted
                return promoted
        return piece             
    
    def _set_start_pieces(self):
        rows_to_fill = 3 if self.boardSize == 8 else 4

        for row in range(self.boardSize):
            for col in range(self.boardSize):
                
                if (row + col) % 2 == 1:
                    if row < rows_to_fill:
                        self.board[row] [col] = Man(Color.BLACK, row, col)
                    elif row >= self.boardSize - rows_to_fill:
                        self.board[row] [col] = Man(Color.WHITE, row, col)

    def _path_has_capture(self, path: list[tuple[int, int]]) -> bool:
        if len(path) == 1:
            r1, c1 = path[0]
            piece = self.getPiece(r1, c1)
            if piece:  
                return False
        
            return False
        for (r1, c1), (r2, c2) in zip(path, path[1:]):
            if abs(r2 - r1) > 1 or abs(c2 - c1) > 1:
                return True
        return False

    def _is_within_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.boardSize and 0 <= col < self.boardSize
    
    def is_game_over(self) -> Optional[Color]:
        white_moves = self.getAllValidMoves(Color.WHITE)
        black_moves = self.getAllValidMoves(Color.BLACK)
        if not white_moves and not black_moves:
            return None  # Draw
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