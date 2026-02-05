from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .move import Move
from .pieces import Piece, Color, Man, King
from .hash import compute_board_hash, zobrist_piece_key, zobrist_turn_key


MoveMap = dict[Piece, tuple[Move, ...]]
MoveMapByStart = dict[tuple[int, int], tuple[Move, ...]]
BoardStatePiece = tuple[int, int, str, bool, int]
BoardState = tuple[int, str, tuple[BoardStatePiece, ...]]


@dataclass(frozen=True, slots=True)
class UndoRecord:
    prev_turn: Color
    prev_hash: int
    piece_before: Piece
    piece_after: Piece
    start: tuple[int, int]
    end: tuple[int, int]
    captured: tuple[Piece, ...]
    captured_positions: tuple[tuple[int, int], ...]


class Board:
    def __init__(self, boardSize: int = 8) -> None:
        self.board: list[list[Optional[Piece]]] = [
            [None for _ in range(boardSize)] for _ in range(boardSize)
        ]
        self.boardSize = boardSize
        self.turn = Color.WHITE
        self._set_start_pieces()
        self.zobrist_hash = compute_board_hash(self)
        self.use_move_cache = True
        self.moves_cache_max_entries = self._DEFAULT_MOVES_CACHE_MAX
        self._moves_cache: dict[tuple[int, int, Color], MoveMapByStart] = {}

    _DEFAULT_MOVES_CACHE_MAX = 20_000

    @classmethod
    def empty(cls, boardSize: int, *, turn: Color = Color.WHITE) -> "Board":
        board = cls.__new__(cls)
        board.boardSize = boardSize
        board.board = [[None for _ in range(boardSize)] for _ in range(boardSize)]
        board.turn = turn
        board.zobrist_hash = zobrist_turn_key(turn)
        board.use_move_cache = True
        board.moves_cache_max_entries = board._DEFAULT_MOVES_CACHE_MAX
        board._moves_cache = {}
        return board

    def to_state(self) -> BoardState:
        pieces: list[BoardStatePiece] = []
        for row in range(self.boardSize):
            for col in range(self.boardSize):
                piece = self.board[row][col]
                if piece is None:
                    continue
                pieces.append((row, col, piece.color.value, piece.is_king, piece.id))
        return (self.boardSize, self.turn.value, tuple(pieces))

    @classmethod
    def from_state(cls, state: BoardState) -> "Board":
        board_size, turn_value, pieces = state
        turn = Color[turn_value.upper()]
        board = cls.empty(board_size, turn=turn)
        for row, col, color_value, is_king, identifier in pieces:
            color = Color[color_value.upper()]
            piece: Piece
            if is_king:
                piece = King(color, row, col, identifier=identifier)
            else:
                piece = Man(color, row, col, identifier=identifier)
            board.board[row][col] = piece
            board.zobrist_hash ^= zobrist_piece_key(board_size, row, col, piece)
        return board
    
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

    def _resolve_moves_by_start(self, moves_by_start: MoveMapByStart) -> MoveMap:
        resolved: MoveMap = {}
        for (row, col), moves in moves_by_start.items():
            piece = self.getPiece(row, col)
            if piece is None:
                continue
            resolved[piece] = moves
        return resolved

    def getAllValidMoves(self, color: Color) -> MoveMap:
        cache_key = (self.boardSize, self.zobrist_hash, color)
        if self.use_move_cache:
            cached = self._moves_cache.get(cache_key)
            if cached is not None:
                return self._resolve_moves_by_start(cached)

        capture_map: MoveMapByStart = {}
        quiet_map: MoveMapByStart = {}

        for piece in self.getAllPieces():
            if piece.color != color:
                continue
            moves = piece.possibleMoves(self)
            if not moves:
                continue

            capture_moves = [move for move in moves if move.is_capture]
            if capture_moves:
                capture_map[piece.position] = tuple(capture_moves)
            else:
                quiet_map[piece.position] = tuple(moves)


        if not capture_map:
            result = quiet_map
            if self.use_move_cache:
                if len(self._moves_cache) < self.moves_cache_max_entries:
                    self._moves_cache[cache_key] = result
            return self._resolve_moves_by_start(result)

        if self.boardSize != 8:
            capture_map = self._filter_majority_captures(capture_map)

        result = capture_map
        if self.use_move_cache:
            if len(self._moves_cache) < self.moves_cache_max_entries:
                self._moves_cache[cache_key] = result
        return self._resolve_moves_by_start(result)

    def _filter_majority_captures(self, capture_map: MoveMapByStart) -> MoveMapByStart:
        """International draughts: enforce majority capture.

        Keep only capture moves that capture the most pieces. If tied, prefer moves
        that capture the most kings.
        """
        all_moves = [move for moves in capture_map.values() for move in moves]
        if not all_moves:
            return capture_map

        max_captures = max(len(move.captures) for move in all_moves)
        by_capture_count: MoveMapByStart = {}
        for start, moves in capture_map.items():
            filtered = [move for move in moves if len(move.captures) == max_captures]
            if filtered:
                by_capture_count[start] = tuple(filtered)
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
        majority: MoveMapByStart = {}
        for start, moves in by_capture_count.items():
            filtered = [move for move in moves if kings_captured(move) == max_kings]
            if filtered:
                majority[start] = tuple(filtered)
        return majority if majority else by_capture_count


    def movePiece(self, piece: Piece, move: Move) -> list[Piece]:
        undo = self.make_move(piece, move)
        return list(undo.captured)

    def make_move(self, piece: Piece, move: Move) -> UndoRecord:
        if not move.steps:
            raise ValueError("Move must contain at least one destination step.")
        if move.start != (piece.row, piece.col):
            raise ValueError("Move start does not match piece position.")
        if self.getPiece(piece.row, piece.col) is not piece:
            raise ValueError("Piece must occupy its recorded position before moving.")

        prev_turn = self.turn
        prev_hash = self.zobrist_hash

        captured: list[Piece] = []
        captured_positions: list[tuple[int, int]] = []

        old_row, old_col = piece.row, piece.col
        start = (old_row, old_col)

        capture_steps = move.captures if move.is_capture else ()
        if move.is_capture and len(capture_steps) != len(move.steps):
            raise ValueError("Capture move must provide one capture coordinate per step.")

        for idx, (new_row, new_col) in enumerate(move.steps):
            if not self._is_within_bounds(new_row, new_col):
                raise ValueError("Move path steps must stay within the board.")
            occupant = self.getPiece(new_row, new_col)
            if occupant is not None:
                raise ValueError("Destination square must be empty.")

            self.board[old_row][old_col] = None
            self.zobrist_hash ^= zobrist_piece_key(self.boardSize, old_row, old_col, piece)

            if move.is_capture:
                cap_row, cap_col = capture_steps[idx]
                target = self.getPiece(cap_row, cap_col)
                if target is None or target.color == piece.color:
                    raise RuntimeError("Capture move references a missing or friendly piece.")
                self.board[cap_row][cap_col] = None
                self.zobrist_hash ^= zobrist_piece_key(self.boardSize, cap_row, cap_col, target)
                captured.append(target)
                captured_positions.append((cap_row, cap_col))

            self.board[new_row][new_col] = piece
            piece.move(new_row, new_col)
            self.zobrist_hash ^= zobrist_piece_key(self.boardSize, new_row, new_col, piece)

            old_row, old_col = new_row, new_col

        piece_before = piece
        piece_after = piece
        promoted = self._handle_promotion(piece)
        if promoted is not piece:
            self.board[old_row][old_col] = None
            self.zobrist_hash ^= zobrist_piece_key(self.boardSize, old_row, old_col, piece)
            self.board[old_row][old_col] = promoted
            self.zobrist_hash ^= zobrist_piece_key(self.boardSize, old_row, old_col, promoted)
            piece_after = promoted

        self.turn = Color.BLACK if self.turn == Color.WHITE else Color.WHITE
        self.zobrist_hash ^= zobrist_turn_key(prev_turn) ^ zobrist_turn_key(self.turn)

        return UndoRecord(
            prev_turn=prev_turn,
            prev_hash=prev_hash,
            piece_before=piece_before,
            piece_after=piece_after,
            start=start,
            end=(old_row, old_col),
            captured=tuple(captured),
            captured_positions=tuple(captured_positions),
        )

    def unmake_move(self, undo: UndoRecord) -> None:
        end_row, end_col = undo.end
        self.board[end_row][end_col] = None

        for piece, (row, col) in zip(undo.captured, undo.captured_positions):
            piece.move(row, col)
            self.board[row][col] = piece

        start_row, start_col = undo.start
        undo.piece_before.move(start_row, start_col)
        self.board[start_row][start_col] = undo.piece_before

        self.turn = undo.prev_turn
        self.zobrist_hash = undo.prev_hash
    
    def copy(self) -> "Board":
        new_board = Board.empty(self.boardSize, turn=self.turn)
        new_board.use_move_cache = self.use_move_cache
        new_board.moves_cache_max_entries = self.moves_cache_max_entries
        for r in range(self.boardSize):
            for c in range(self.boardSize):
                p = self.getPiece(r, c)
                if p:
                    clone = p.getCopy()
                    new_board.board[r][c] = clone
                    new_board.zobrist_hash ^= zobrist_piece_key(self.boardSize, r, c, clone)
        return new_board

    def simulateMove(self, move: Move) -> "Board":
        board_copy = self.copy()
        piece = board_copy.getPiece(*move.start)
        if piece is None:
            raise ValueError("No piece found at move start when simulating move.")
        board_copy.movePiece(piece, move)
        return board_copy

    def compute_hash(self) -> int:
        return self.zobrist_hash

    def recompute_hash(self) -> int:
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
        pieces = self.getAllPieces()
        white_count = sum(1 for piece in pieces if piece.color == Color.WHITE)
        black_count = len(pieces) - white_count

        if white_count == 0 and black_count == 0:
            return None
        if white_count == 0:
            return Color.BLACK
        if black_count == 0:
            return Color.WHITE

        current = self.turn
        current_moves = self.getAllValidMoves(current)
        if current_moves:
            return None
        return Color.BLACK if current == Color.WHITE else Color.WHITE





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
