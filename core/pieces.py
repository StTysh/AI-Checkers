from enum import Enum
from board import Board

class Color(Enum):
    BLACK = "black"
    WHITE = "white"

class Piece:
    def __init__ (self, color: Color, row: int, col: int):
        self.color = color
        self.row = row
        self.col = col
        self.isKing = False

    def move(self,newRaw, newColumn):
        self.row = newRaw
        self.col = newColumn

    def possibleMoves(board) -> list:
        return []
    
    def __repr__(self) -> str:
        return f'Color: {self.color}, King: {self.isKing}, Row: {self.row}, Column: {self.col}'
    
    def getCopy(self): return Piece(self.color,self.row,self.col)

class King(Piece):
    def __init__(self, color: Color, row: int, col: int):
        super().__init__(color, row, col)
        self.isKing = True
    def possibleMoves(board: Board) -> list:
        return []
    
    def getCopy(self): return King(self.color, self.row, self.col)
    
class Men(Piece):
    def __init__(self, color: Color, row: int, col: int):
        super().__init__(color, row, col)       

    def promote(self) -> King:
        if(not self.isKing):
            return King(self.color, self.row, self.col)    
    
    def getCopy(self): return Men(self.color, self.row, self.col)

    def possibleMoves(board) -> list:
        return []

