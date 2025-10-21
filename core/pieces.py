from enum import Enum
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from board import Board

class Color(Enum):
    BLACK = "black"
    WHITE = "white"

class Piece:
    def __init__ (self, color: Color, row: int, col: int) -> None:
        self.color = color
        self.row = row
        self.col = col
        self.is_king = False

    def move(self, new_row: int, new_col: int) -> None:
        self.row = new_row
        self.col = new_col

    def possibleMoves(self, board: "Board") -> list[list[tuple[int, int]]]:
        return []
    
    def __repr__(self) -> str:
        return f'Color: {self.color}, King: {self.is_king}, Row: {self.row}, Column: {self.col}'
    
    def getCopy(self): return Piece(self.color,self.row,self.col)

class King(Piece):
    def __init__(self, color: Color, row: int, col: int):
        super().__init__(color, row, col)
        self.is_king = True
    
    def getCopy(self) -> Piece: 
        return King(self.color, self.row, self.col)
    
    def possibleMoves(self, board: "Board") -> list[list[tuple[int, int]]]:
        moves = []
        captures = []
        directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)] 

        if board.boardSize == 8:
            for dr, dc in directions:
                new_r, new_c = self.row + dr, self.col + dc
                if board._is_within_bounds(new_r, new_c) and not board.getPiece(new_r, new_c):
                    moves.append([(new_r, new_c)])

            def dfs_english(r, c, visited: set) -> list[list[tuple[int, int]]]:
                paths = []
                for dr, dc in directions:
                    mr, mc = r + dr, c + dc
                    er, ec = r + 2 * dr, c + 2 * dc
                    if (
                        board._is_within_bounds(er, ec)
                        and board.getPiece(mr, mc)
                        and board.getPiece(mr, mc).color != self.color
                        and not board.getPiece(er, ec)
                        and (mr, mc) not in visited
                    ):
                        new_visited = visited | {(mr, mc)}
                        next_caps = dfs_english(er, ec, new_visited)
                        if next_caps:
                            for seq in next_caps:
                                paths.append([(er, ec)] + seq)
                        else:
                            paths.append([(er, ec)])
                return paths

            captures = dfs_english(self.row, self.col, set())

        else:  
            for dr, dc in directions:
                r, c = self.row + dr, self.col + dc
                while board._is_within_bounds(r, c) and not board.getPiece(r, c):
                    moves.append([(r, c)])
                    r += dr
                    c += dc

            def dfs_international(r, c, visited: set) -> list[list[tuple[int, int]]]:
                paths = []
                for dr, dc in directions:
                    step_r, step_c = r + dr, c + dc
                    enemy = None
                    while board._is_within_bounds(step_r, step_c):
                        target = board.getPiece(step_r, step_c)
                        if target:
                            if target.color == self.color or (step_r, step_c) in visited:
                                break
                            enemy = (step_r, step_c)
                            break
                        step_r += dr
                        step_c += dc
                    if enemy:
                        after_r, after_c = enemy[0] + dr, enemy[1] + dc
                        while board._is_within_bounds(after_r, after_c) and not board.getPiece(after_r, after_c):
                            new_visited = visited | {enemy}
                            next_caps = dfs_international(after_r, after_c, new_visited)
                            if next_caps:
                                for seq in next_caps:
                                    paths.append([(after_r, after_c)] + seq)
                            else:
                                paths.append([(after_r, after_c)])
                            after_r += dr
                            after_c += dc
                return paths

            captures = dfs_international(self.row, self.col, set())

        return captures if captures else moves
    

class Man(Piece):
    def __init__(self, color: Color, row: int, col: int):
        super().__init__(color, row, col)       

    def promote(self) -> King:
        return King(self.color, self.row, self.col)    
    
    def getCopy(self) -> Piece: 
        return Man(self.color, self.row, self.col)

    def possibleMoves(self,board: "Board") -> list[list[tuple[int, int]]]:
        moves = []
        captures = []

        forward_dirs = [(-1, -1), (-1, 1)] if self.color == Color.WHITE else [(1, -1), (1, 1)]

        if board.boardSize == 8:
            capture_dirs = forward_dirs  
        else:
            capture_dirs = [(-1, -1), (-1, 1), (1, -1), (1, 1)]

       
        for dr, dc in forward_dirs:
            new_r, new_c = self.row + dr, self.col + dc
            if board._is_within_bounds(new_r, new_c) and not board.getPiece(new_r, new_c):
                moves.append([(new_r, new_c)])

        
        def dfs_captures(r, c, visited: set[tuple[int, int]]) -> list[list[tuple[int, int]]]:
            local_caps = []
            for dr, dc in capture_dirs:
                mid_r, mid_c = r + dr, c + dc
                end_r, end_c = r + 2 * dr, c + 2 * dc
                if (
                    board._is_within_bounds(end_r, end_c)
                    and board.getPiece(mid_r, mid_c)
                    and board.getPiece(mid_r, mid_c).color != self.color
                    and not board.getPiece(end_r, end_c)
                    and (mid_r, mid_c) not in visited
                ):
                    new_visited = visited.copy()
                    new_visited.add((mid_r, mid_c))
                    next_moves = dfs_captures(end_r, end_c, new_visited)
                    if next_moves:
                        for seq in next_moves:
                            local_caps.append([(end_r, end_c)] + seq)
                    else:
                        local_caps.append([(end_r, end_c)])
            return local_caps

        captures = dfs_captures(self.row, self.col, set())

        
        return captures if captures else moves

    
