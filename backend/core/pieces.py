from __future__ import annotations

from enum import Enum
from itertools import count
from typing import TYPE_CHECKING, Optional

from .move import Coordinate, Move

if TYPE_CHECKING:
    from .board import Board


MoveList = list[Move]
_PIECE_ID_COUNTER = count()


class Color(Enum):
    BLACK = "black"
    WHITE = "white"


class Piece:
    def __init__(self, color: Color, row: int, col: int, *, identifier: Optional[int] = None) -> None:
        self.color = color
        self.row = row
        self.col = col
        self.is_king = False
        self.id = identifier if identifier is not None else next(_PIECE_ID_COUNTER)

    def move(self, new_row: int, new_col: int) -> None:
        self.row = new_row
        self.col = new_col

    @property
    def position(self) -> Coordinate:
        return (self.row, self.col)

    def possibleMoves(self, board: "Board") -> MoveList:
        return []
    
    def getCopy(self) -> "Piece":
        clone = self.__class__(self.color, self.row, self.col, identifier=self.id)
        clone.is_king = self.is_king
        return clone

    def __repr__(self) -> str:
        piece_type = "K" if self.is_king else "M"
        return f"{piece_type}({self.color.name},{self.row},{self.col})"

class King(Piece):
    def __init__(self, color: Color, row: int, col: int, *, identifier: Optional[int] = None):
        super().__init__(color, row, col, identifier=identifier)
        self.is_king = True
    
    def getCopy(self) -> "Piece":
        return King(self.color, self.row, self.col, identifier=self.id)
    
    def possibleMoves(self, board: "Board") -> MoveList:
        origin = self.position
        moves: MoveList = []
        capture_moves: MoveList = []
        directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]

        if board.boardSize == 8:
            for dr, dc in directions:
                new_r, new_c = self.row + dr, self.col + dc
                if board._is_within_bounds(new_r, new_c) and not board.getPiece(new_r, new_c):
                    moves.append(Move(start=origin, steps=((new_r, new_c),)))

            def dfs_english(
                r: int,
                c: int,
                path: list[Coordinate],
                captured: list[Coordinate],
                visited: set[Coordinate],
            ) -> None:
                extended = False
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
                        extended = True
                        dfs_english(
                            er,
                            ec,
                            path + [(er, ec)],
                            captured + [(mr, mc)],
                            visited | {(mr, mc)},
                        )
                if not extended and captured:
                    capture_moves.append(
                        Move(start=origin, steps=tuple(path), captures=tuple(captured))
                    )

            dfs_english(self.row, self.col, [], [], set())

        else:
            for dr, dc in directions:
                r, c = self.row + dr, self.col + dc
                while board._is_within_bounds(r, c) and not board.getPiece(r, c):
                    moves.append(Move(start=origin, steps=((r, c),)))
                    r += dr
                    c += dc

            def dfs_international(
                r: int,
                c: int,
                path: list[Coordinate],
                captured: list[Coordinate],
                visited: set[Coordinate],
            ) -> None:
                extended = False
                for dr, dc in directions:
                    step_r, step_c = r + dr, c + dc
                    enemy: Coordinate | None = None
                    while board._is_within_bounds(step_r, step_c):
                        target = board.getPiece(step_r, step_c)
                        if target:
                            if target.color == self.color or (step_r, step_c) in visited:
                                enemy = None
                            else:
                                enemy = (step_r, step_c)
                            break
                        step_r += dr
                        step_c += dc
                    if not enemy:
                        continue
                    after_r, after_c = enemy[0] + dr, enemy[1] + dc
                    while board._is_within_bounds(after_r, after_c) and not board.getPiece(after_r, after_c):
                        extended = True
                        dfs_international(
                            after_r,
                            after_c,
                            path + [(after_r, after_c)],
                            captured + [enemy],
                            visited | {enemy},
                        )
                        after_r += dr
                        after_c += dc
                if not extended and captured:
                    capture_moves.append(
                        Move(start=origin, steps=tuple(path), captures=tuple(captured))
                    )

            dfs_international(self.row, self.col, [], [], set())

        return capture_moves if capture_moves else moves
    

class Man(Piece):
    def __init__(self, color: Color, row: int, col: int, *, identifier: Optional[int] = None):
        super().__init__(color, row, col, identifier=identifier)

    def promote(self) -> King:
        return King(self.color, self.row, self.col, identifier=self.id)

    def getCopy(self) -> "Piece":
        return Man(self.color, self.row, self.col, identifier=self.id)

    def possibleMoves(self, board: "Board") -> MoveList:
        origin = self.position
        moves: MoveList = []
        capture_moves: MoveList = []

        forward_dirs = [(-1, -1), (-1, 1)] if self.color == Color.WHITE else [(1, -1), (1, 1)]

        if board.boardSize == 8:
            capture_dirs = forward_dirs
        else:
            capture_dirs = [(-1, -1), (-1, 1), (1, -1), (1, 1)]

        for dr, dc in forward_dirs:
            new_r, new_c = self.row + dr, self.col + dc
            if board._is_within_bounds(new_r, new_c) and not board.getPiece(new_r, new_c):
                moves.append(Move(start=origin, steps=((new_r, new_c),)))

        def dfs_captures(
            r: int,
            c: int,
            path: list[Coordinate],
            captured: list[Coordinate],
            visited: set[Coordinate],
        ) -> None:
            extended = False
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
                    extended = True
                    dfs_captures(
                        end_r,
                        end_c,
                        path + [(end_r, end_c)],
                        captured + [(mid_r, mid_c)],
                        visited | {(mid_r, mid_c)},
                    )
            if not extended and captured:
                capture_moves.append(
                    Move(start=origin, steps=tuple(path), captures=tuple(captured))
                )

        dfs_captures(self.row, self.col, [], [], set())

        return capture_moves if capture_moves else moves


