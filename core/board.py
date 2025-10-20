from pieces import Piece, Color, Men, King
from typing import Optional



class Board: 
    def __init__(self, boardSize: int):
        self.board = [[None for _ in range(boardSize)] for _ in range(boardSize)]
        self.boardSize = boardSize
        self._set_start_pieces()
    
    def printBoard(self):
        for row in self.board:
            print(" ".join(str(cell) if cell else "." for cell in row))

    def getPiece(self, row: int, col: int) -> Optional[Piece]:
        if(self._is_within_bound(row,col)):
            return self.board[row][col]
        else: return 

    def getAllPieces(self) -> list[Piece] :
        pieces = []
        for row in range(self.boardSize):
            for col in range(self.boardSize):                
                if (row + col) % 2 == 1:
                    piece = self.getPiece(row, col)
                    if(piece): pieces.append(piece)

    def getValidMoves(self, piece: Piece):
        return piece.possibleMoves()

    def getAllValidMoves(self, color: Color):
        validMoves = {}
        for piece in self.getAllPieces():
            if piece.color == color:
                moves = piece.possibleMoves()
                if(moves): validMoves[piece] = moves
        return validMoves


    def movePiece(self, piece: Piece, newRow: int, newCol: int):
        oldRow, oldCol = piece.row, piece.col
        self.board[oldRow][oldCol] = None
        self.board[newRow][newCol] = piece
        piece.move(newRow, newCol)

        self._handle_captures(piece, oldRow, oldCol, newRow, newCol)  

        self._handle_promotion(piece)
    
    def copy(self):
        new_board = Board(self.boardSize)
        for row in range(self.boardSize):
            for col in range(self.boardSize):
                piece = self.getPiece(row,col)
                if piece:
                    new_piece = piece.getCopy()
                    new_board.board[row][col] = new_piece
        return new_board

    def _remove_piece(self, piece: Piece):
        if(piece and self.board[piece.row][piece.col] == piece):
            self.board[piece.row][piece.col] = None

    def _handle_captures(self, piece, oldRow, oldCol, newRow, newCol):
        captured = None
        if abs(newRow - oldRow) == 2:
            midRow = (oldRow + newRow) // 2
            midCol = (oldCol + newCol) // 2
            captured_piece = self.board[midRow][midCol]
            if captured_piece and captured_piece.color != piece.color:
                self._remove_piece(captured_piece)
                captured = captured_piece
            return captured        
        
        if self.boardsize == 10 and piece.isKing:
            direction_row = 1 if newRow > oldRow else -1
            direction_col = 1 if newCol > oldCol else -1
            r, c = oldRow + direction_row, oldCol + direction_col
            while r != newRow and c != newCol:
                mid_piece = self.board[r][c]
                if mid_piece and mid_piece.color != piece.color:
                    self._remove_piece(mid_piece)
                    captured = mid_piece
                    break  
                r += direction_row
                c += direction_col
        
        return captured
    

    def _handle_promotion(self, piece):
        if not piece.isKing:
            if (piece.color == Color.WHITE and piece.row == 0) or (piece.color == Color.BLACK and piece.row == (self.boardsize - 1)):
                self.board[piece.row][piece.col] = Men(piece).promote()

                   
    def _king_can_continue_capture(self, piece: Piece):
        directions = [(-1,-1), (-1,1), (1,-1), (1,1)]
        for dr, dc in directions:
            r, c = piece.row + dr, piece.col + dc
            while 0 <= r < self.boardsize and 0 <= c < self.boardsize:
                if self.board[r][c] is None:
                    r += dr; c += dc
                    continue
                elif self.board[r][c].color != piece.color:
                    next_r, next_c = r + dr, c + dc
                    if 0 <= next_r < self.boardsize and 0 <= next_c < self.boardsize and self.board[next_r][next_c] is None:
                        return True
                    break
                else:
                    break
        return False
    
    def _set_start_pieces(self):
        rows_to_fill = 3 if self.boardSize == 8 else 4

        for row in range(self.boardSize):
            for col in range(self.boardSize):
                
                if (row + col) % 2 == 1:
                    if row < rows_to_fill:
                        self.board[row][col] = Men(Color.BLACK, row, col)
                    elif row >= self.boardSize - rows_to_fill:
                        self.board[row][col] = Piece(Color.WHITE, row, col)

    def _is_within_bound(self, row, col):
        return True if ((-1 < row < self.boardSize) and (-1 < col < self.boardSize)) else False

    def is_game_over(self) -> Optional[Color]:
        if (self.getAllValidMoves(Color.WHITE)): return Color.WHITE
        elif (self.getAllValidMoves(Color.BLACK)): return Color.BLACK
        else: return None






#|       |  **0** |  **1** |  **2** |  **3** |  **4** |  **5** |  **6** |  **7** |
#| ----- | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ |
#|	     |	      |	       |        |        |        |        |        |        |
#| **0** | [0][0] | [0][1] | [0][2] | [0][3] | [0][4] | [0][5] | [0][6] | [0][7] |
#|	     |	      |	       |        |        |        |        |        |        |
#| ----- | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ |
#|	     |	      |	       |        |        |        |        |        |        |
#| **1** | [1][0] | [1][1] | [1][2] | [1][3] | [1][4] | [1][5] | [1][6] | [1][7] |
#|	     |	      |	       |        |        |        |        |        |        |
#| ----- | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ |
#|	     |	      |	       |        |        |        |        |        |        |
#| **2** | [2][0] | [2][1] | [2][2] | [2][3] | [2][4] | [2][5] | [2][6] | [2][7] |
#|	     |	      |	       |        |        |        |        |        |        |
#| ----- | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ |
#|	     |	      |	       |        |        |        |        |        |        |
#| **3** | [3][0] | [3][1] | [3][2] | [3][3] | [3][4] | [3][5] | [3][6] | [3][7] |
#|	     |	      |	       |        |        |        |        |        |        |
#| ----- | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ |
#|	     |	      |	       |        |        |        |        |        |        |
#| **4** | [4][0] | [4][1] | [4][2] | [4][3] | [4][4] | [4][5] | [4][6] | [4][7] |
#|	     |	      |	       |        |        |        |        |        |        |     
#| ----- | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ |
#|	     |	      |	       |        |        |        |        |        |        |
#| **5** | [5][0] | [5][1] | [5][2] | [5][3] | [5][4] | [5][5] | [5][6] | [5][7] |
#|	     |	      |	       |        |        |        |        |        |        |
#| ----- | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ |
#|	     |	      |	       |        |        |        |        |        |        |
#| **6** | [6][0] | [6][1] | [6][2] | [6][3] | [6][4] | [6][5] | [6][6] | [6][7] |
#|	     |	      |	       |        |        |        |        |        |        |
#| ----- | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ |
#|	     |	      |	       |        |        |        |        |        |        |
#| **7** | [7][0] | [7][1] | [7][2] | [7][3] | [7][4] | [7][5] | [7][6] | [7][7] |
#|	     |	      |	       |        |        |        |        |        |        |
#| ----- | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ |