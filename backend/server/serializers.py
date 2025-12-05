from __future__ import annotations

from collections import Counter
from typing import Any

from core.game import Game
from core.move import Move
from core.pieces import Color, Piece
from core.player import PlayerController


def _coord_tuple_to_dict(coord: tuple[int, int]) -> dict[str, int]:
    row, col = coord
    return {"row": row, "col": col}


def serialize_piece(piece: Piece) -> dict[str, Any]:
    return {
        "id": piece.id,
        "row": piece.row,
        "col": piece.col,
        "color": piece.color.value,
        "isKing": piece.is_king,
    }


def serialize_move(move: Move) -> dict[str, Any]:
    return {
        "start": _coord_tuple_to_dict(move.start),
        "steps": [_coord_tuple_to_dict(step) for step in move.steps],
        "captures": [_coord_tuple_to_dict(capture) for capture in move.captures],
        "isCapture": move.is_capture,
    }


def serialize_controller(controller: PlayerController) -> dict[str, str]:
    return {"kind": controller.kind.value, "name": controller.name}


def serialize_game(
    game: Game,
    variant: str,
    player_settings: dict[Color, dict[str, Any]],
) -> dict[str, Any]:
    pieces = [serialize_piece(piece) for piece in game.board.getAllPieces()]
    total_counts = Counter(piece["color"] for piece in pieces)
    king_counts = Counter(
        piece["color"]
        for piece in pieces
        if piece["isKing"]
    )

    moves_map = game.getValidMoves()
    capture_required = any(move.is_capture for options in moves_map.values() for move in options)

    last_record = game.move_history[-1] if game.move_history else None
    last_move = serialize_move(last_record.move) if last_record else None

    return {
        "boardSize": game.board.boardSize,
        "variant": variant,
        "turn": game.current_player.value,
        "winner": game.winner.value if game.winner else None,
        "pieces": pieces,
        "pieceCounts": {
            "white": {
                "total": total_counts.get("white", 0),
                "kings": king_counts.get("white", 0),
            },
            "black": {
                "total": total_counts.get("black", 0),
                "kings": king_counts.get("black", 0),
            },
        },
        "mandatoryCapture": capture_required,
        "moveCount": len(game.move_history),
        "canUndo": bool(game.move_history),
        "canRedo": False,
        "lastMove": last_move,
        "players": {
            "white": serialize_controller(game.getPlayer(Color.WHITE)),
            "black": serialize_controller(game.getPlayer(Color.BLACK)),
        },
        "playerConfig": {
            "white": player_settings[Color.WHITE].copy(),
            "black": player_settings[Color.BLACK].copy(),
        },
    }
