from __future__ import annotations

import pygame
from pygame import gfxdraw

from core.game import Game
from core.move import Coordinate, Move
from core.pieces import Color, Piece


class CheckersGUI:
    def __init__(self, game: Game, square_size: int = 80, info_height: int = 230) -> None:
        self.game = game
        self.square_size = square_size
        self.board_size = self.game.board.boardSize
        self.board_pixels = self.square_size * self.board_size
        self.info_height = info_height

        self.margin = 40
        self.window_width = self.board_pixels + self.margin * 2
        self.window_height = self.board_pixels + self.info_height + self.margin * 2

        self.screen = pygame.display.set_mode((self.window_width, self.window_height))
        pygame.display.set_caption("Checkers")

        self.font = pygame.font.SysFont("arial", 24)
        self.small_font = pygame.font.SysFont("arial", 16)
        self.title_font = pygame.font.SysFont("arial", 28, bold=True)
        self.king_font = pygame.font.SysFont("arial", 22, bold=True)
        self.clock = pygame.time.Clock()

        self.selected_piece: Piece | None = None
        self.destination_map: dict[Coordinate, list[Move]] = {}
        self.hover_cell: Coordinate | None = None
        self.valid_moves: dict[Piece, list[Move]] = {}
        self.capture_available = False
        self.piece_surfaces: dict[tuple[Color, bool], pygame.Surface] = {}

        self.colors = {
            "light": (233, 210, 173),
            "dark": (145, 104, 66),
            "highlight": (246, 227, 90),
            "selected": (252, 142, 80),
            "white_piece": (245, 245, 245),
            "black_piece": (35, 35, 35),
            "outline": (25, 25, 25),
            "background": (30, 34, 45),
            "background_accent": (50, 58, 74),
            "info_bg": (40, 46, 60),
            "panel_border": (86, 94, 110),
            "text": (230, 230, 230),
            "coordinate": (210, 210, 210),
            "board_frame": (82, 54, 29),
            "board_inset": (56, 38, 23),
            "shadow": (0, 0, 0),
            "badge_bg": (255, 255, 255),
            "badge_text": (55, 55, 55),
            "king": (255, 215, 0),
        }

        self.background_surface = self._build_background_surface(self.window_width, self.window_height)

        self._refresh_valid_moves()

    def run(self) -> None:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        running = False
                    elif event.key == pygame.K_r:
                        self.game.reset()
                        self.selected_piece = None
                        self.destination_map.clear()
                        self._refresh_valid_moves()
                    elif event.key == pygame.K_u:
                        self.game.undoMove()
                        self.selected_piece = None
                        self.destination_map.clear()
                        self._refresh_valid_moves()
                elif event.type == pygame.MOUSEMOTION:
                    self.hover_cell = self._board_coords_from_pos(event.pos)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_click(event.pos)

            self._draw()
            pygame.display.flip()
            self.clock.tick(60)

    def _handle_click(self, pos: tuple[int, int]) -> None:
        cell = self._board_coords_from_pos(pos)
        if cell is None or self.game.winner:
            return

        if self.selected_piece and cell in self.destination_map:
            move_options = self.destination_map[cell]
            chosen_move = move_options[0]
            if self.game.makeMove(self.selected_piece, chosen_move):
                self.selected_piece = None
                self.destination_map.clear()
                self._refresh_valid_moves()
            return

        row, col = cell
        piece = self.game.board.getPiece(row, col)
        if not piece or piece.color != self.game.current_player:
            self.selected_piece = None
            self.destination_map.clear()
            return

        self.selected_piece = piece
        self.destination_map = self._build_destination_map(piece)

    def _build_destination_map(self, piece: Piece) -> dict[Coordinate, list[Move]]:
        moves = self.valid_moves.get(piece, [])
        destination_map: dict[Coordinate, list[Move]] = {}
        for move in moves:
            destination_map.setdefault(move.end, []).append(move)
        return destination_map

    def _refresh_valid_moves(self) -> None:
        self.valid_moves = self.game.getValidMoves()
        self.capture_available = any(
            move.is_capture
            for move_list in self.valid_moves.values()
            for move in move_list
        )

    def _board_coords_from_pos(self, pos: tuple[int, int]) -> Coordinate | None:
        x, y = pos
        x -= self.margin
        y -= self.margin
        if x < 0 or y < 0 or x >= self.board_pixels or y >= self.board_pixels:
            return None
        return (y // self.square_size, x // self.square_size)

    def _draw(self) -> None:
        self._draw_background()
        self._draw_board()
        self._draw_selection()
        self._draw_pieces()
        self._draw_info_panel()

    def _draw_board(self) -> None:
        board_rect = pygame.Rect(self.margin, self.margin, self.board_pixels, self.board_pixels)

        shadow_rect = board_rect.inflate(32, 32)
        shadow_surface = pygame.Surface(shadow_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(
            shadow_surface,
            (*self.colors["shadow"], 120),
            shadow_surface.get_rect(),
            border_radius=24,
        )
        self.screen.blit(shadow_surface, shadow_rect.move(-16, 18))

        frame_rect = board_rect.inflate(20, 20)
        pygame.draw.rect(self.screen, self.colors["board_frame"], frame_rect, border_radius=20)
        inset_rect = frame_rect.inflate(-10, -10)
        pygame.draw.rect(self.screen, self.colors["board_inset"], inset_rect, border_radius=16)

        for row in range(self.board_size):
            for col in range(self.board_size):
                color = self.colors["light"] if (row + col) % 2 == 0 else self.colors["dark"]
                rect = pygame.Rect(
                    self.margin + col * self.square_size,
                    self.margin + row * self.square_size,
                    self.square_size,
                    self.square_size,
                )
                pygame.draw.rect(self.screen, color, rect)

        pygame.draw.rect(self.screen, (*self.colors["outline"], 120), board_rect, 2, border_radius=12)
        self._draw_board_grid(board_rect)
        self._draw_coordinates(board_rect)

    def _draw_selection(self) -> None:
        if self.selected_piece:
            row, col = self.selected_piece.row, self.selected_piece.col
            rect = pygame.Rect(
                self.margin + col * self.square_size,
                self.margin + row * self.square_size,
                self.square_size,
                self.square_size,
            )
            pygame.draw.rect(self.screen, self.colors["selected"], rect, 4, border_radius=8)

        for dest in self.destination_map:
            center = self._center_for_cell(*dest)
            highlight_rgba = (*self.colors["highlight"], 140)
            gfxdraw.filled_circle(
                self.screen,
                center[0],
                center[1],
                12,
                highlight_rgba,
            )
            gfxdraw.aacircle(self.screen, center[0], center[1], 12, self.colors["outline"])

        if self.hover_cell and self.hover_cell in self.destination_map:
            center = self._center_for_cell(*self.hover_cell)
            selected_rgba = (*self.colors["selected"], 90)
            gfxdraw.filled_circle(
                self.screen,
                center[0],
                center[1],
                16,
                selected_rgba,
            )
            gfxdraw.aacircle(self.screen, center[0], center[1], 16, self.colors["outline"])

    def _draw_pieces(self) -> None:
        for piece in self.game.board.getAllPieces():
            surface = self._get_piece_surface(piece)
            rect = surface.get_rect(center=self._center_for_cell(piece.row, piece.col))
            shadow = self._build_shadow_surface(surface.get_width())
            shadow_rect = shadow.get_rect(center=(rect.centerx + 3, rect.centery + 4))
            self.screen.blit(shadow, shadow_rect)
            self.screen.blit(surface, rect)

    def _draw_info_panel(self) -> None:
        panel_top = self.margin + self.board_pixels + 60
        info_rect = pygame.Rect(self.margin, panel_top, self.board_pixels, self.info_height - 36)

        panel_surface = pygame.Surface(info_rect.size, pygame.SRCALPHA)
        for y in range(info_rect.height):
            t = y / max(info_rect.height - 1, 1)
            color = self._mix_color(self.colors["info_bg"], self.colors["background_accent"], t * 0.4)
            pygame.draw.line(panel_surface, color, (0, y), (info_rect.width, y))
        pygame.draw.rect(panel_surface, self.colors["panel_border"], panel_surface.get_rect(), 2, border_radius=16)
        self.screen.blit(panel_surface, info_rect.topleft)

        title = self.title_font.render("Match Overview", True, self.colors["text"])
        self.screen.blit(title, (info_rect.left + 20, info_rect.top + 16))

        piece_counts: dict[Color, tuple[int, int]] = {Color.WHITE: (0, 0), Color.BLACK: (0, 0)}
        for piece in self.game.board.getAllPieces():
            count, kings = piece_counts[piece.color]
            piece_counts[piece.color] = (count + 1, kings + int(piece.is_king))

        self._draw_player_panel(info_rect, Color.WHITE, piece_counts[Color.WHITE], align="left")
        self._draw_player_panel(info_rect, Color.BLACK, piece_counts[Color.BLACK], align="right")

        meta_lines = [
            f"Turn {len(self.game.move_history) + 1}",
            f"Current player: {self.game.current_player.value.capitalize()}",
            f"Mandatory capture: {'Yes' if self.capture_available else 'No'}",
            f"Winner: {self.game.winner.value.capitalize() if self.game.winner else 'Pending'}",
            "R: Reset  |  U: Undo  |  Esc/Q: Quit",
        ]
        y_offset = info_rect.top + 80
        for line in meta_lines:
            text_surface = self.small_font.render(line, True, self.colors["text"])
            self.screen.blit(text_surface, (info_rect.left + 24, y_offset))
            y_offset += 22

    def _draw_background(self) -> None:
        self.screen.blit(self.background_surface, (0, 0))

    def _build_background_surface(self, width: int, height: int) -> pygame.Surface:
        surface = pygame.Surface((width, height))
        top_color = self.colors["background_accent"]
        bottom_color = self.colors["background"]
        for y in range(height):
            t = y / max(height - 1, 1)
            blended = self._mix_color(top_color, bottom_color, t)
            pygame.draw.line(surface, blended, (0, y), (width, y))
        vignette = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.ellipse(
            vignette,
            (0, 0, 0, 130),
            pygame.Rect(-width * 0.25, height * 0.4, width * 1.5, height * 1.2),
        )
        surface.blit(vignette, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        return surface

    def _draw_board_grid(self, board_rect: pygame.Rect) -> None:
        grid_surface = pygame.Surface(board_rect.size, pygame.SRCALPHA)
        for i in range(1, self.board_size):
            pygame.draw.line(
                grid_surface,
                (*self.colors["outline"], 35),
                (0, i * self.square_size),
                (board_rect.width, i * self.square_size),
                1,
            )
            pygame.draw.line(
                grid_surface,
                (*self.colors["outline"], 35),
                (i * self.square_size, 0),
                (i * self.square_size, board_rect.height),
                1,
            )
        self.screen.blit(grid_surface, board_rect.topleft)

    def _draw_coordinates(self, board_rect: pygame.Rect) -> None:
        for idx in range(self.board_size):
            letter = chr(ord("A") + idx)
            number = str(self.board_size - idx)
            top_label = self.small_font.render(letter, True, self.colors["coordinate"])
            bottom_label = self.small_font.render(letter, True, self.colors["coordinate"])
            left_label = self.small_font.render(number, True, self.colors["coordinate"])
            right_label = self.small_font.render(number, True, self.colors["coordinate"])

            cx = board_rect.left + idx * self.square_size + self.square_size // 2
            self.screen.blit(top_label, top_label.get_rect(center=(cx, board_rect.top - 18)))
            self.screen.blit(bottom_label, bottom_label.get_rect(center=(cx, board_rect.bottom + 18)))

            cy = board_rect.top + idx * self.square_size + self.square_size // 2
            self.screen.blit(left_label, left_label.get_rect(center=(board_rect.left - 18, cy)))
            self.screen.blit(right_label, right_label.get_rect(center=(board_rect.right + 18, cy)))

    def _draw_player_panel(
        self,
        info_rect: pygame.Rect,
        color: Color,
        stats: tuple[int, int],
        *,
        align: str,
    ) -> None:
        label = color.value.capitalize()
        count, kings = stats
        badge_width = 220
        badge_height = 60
        offset_x = info_rect.left + 20 if align == "left" else info_rect.right - 20 - badge_width
        badge_rect = pygame.Rect(offset_x, info_rect.top + 16, badge_width, badge_height)

        badge_surface = pygame.Surface(badge_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(badge_surface, (*self.colors["shadow"], 90), badge_surface.get_rect(), border_radius=18)
        fill_rect = badge_surface.get_rect().inflate(-4, -4)
        highlight_ratio = 0.15 if color == self.game.current_player else 0.0
        badge_color = self._mix_color(
            self.colors["badge_bg"],
            self.colors["highlight"],
            highlight_ratio,
        )
        pygame.draw.rect(badge_surface, badge_color, fill_rect, border_radius=16)
        pygame.draw.rect(badge_surface, (*self.colors["panel_border"], 160), fill_rect, 1, border_radius=16)
        self.screen.blit(badge_surface, badge_rect.topleft)

        name_text = self.font.render(label, True, self.colors["badge_text"])
        pieces_text = self.small_font.render(f"Pieces: {count}", True, self.colors["badge_text"])
        kings_text = self.small_font.render(f"Kings: {kings}", True, self.colors["badge_text"])

        text_x = badge_rect.left + 18
        text_y = badge_rect.top + 8
        self.screen.blit(name_text, (text_x, text_y))
        self.screen.blit(pieces_text, (text_x, text_y + 26))
        self.screen.blit(kings_text, (text_x + 110, text_y + 26))

    def _center_for_cell(self, row: int, col: int) -> tuple[int, int]:
        return (
            self.margin + col * self.square_size + self.square_size // 2,
            self.margin + row * self.square_size + self.square_size // 2,
        )

    def _get_piece_surface(self, piece: Piece) -> pygame.Surface:
        key = (piece.color, piece.is_king)
        if key in self.piece_surfaces:
            return self.piece_surfaces[key]

        diameter = self.square_size - 14
        radius = diameter // 2
        surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        cx, cy = surface.get_width() // 2, surface.get_height() // 2

        base = self.colors["white_piece"] if piece.color == Color.WHITE else self.colors["black_piece"]
        pygame.draw.circle(surface, base, (cx, cy), radius)
        pygame.draw.circle(surface, self.colors["outline"], (cx, cy), radius, 2)

        if piece.is_king:
            king_color = self.colors["outline"] if piece.color == Color.WHITE else self.colors["king"]
            crown = self.king_font.render("K", True, king_color)
            crown_rect = crown.get_rect(center=(cx, cy))
            surface.blit(crown, crown_rect)

        self.piece_surfaces[key] = surface
        return surface

    def _build_shadow_surface(self, diameter: int) -> pygame.Surface:
        radius = diameter // 2
        shadow_surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        cx, cy = shadow_surface.get_width() // 2, shadow_surface.get_height() // 2
        for r in range(radius, 0, -1):
            alpha = int(70 * (r / radius))
            gfxdraw.filled_circle(shadow_surface, cx, cy, r, (0, 0, 0, alpha))
        return shadow_surface

    @staticmethod
    def _mix_color(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
        clamped = max(0.0, min(1.0, t))
        return tuple(int(a[i] * (1.0 - clamped) + b[i] * clamped) for i in range(3))
