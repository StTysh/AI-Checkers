from __future__ import annotations

from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .schemas import AIMoveRequest, ConfigRequest, MoveRequest, PerformAIMoveRequest, ResetRequest, VariantRequest
from .session import GameSession


def create_app() -> FastAPI:
    app = FastAPI(title="Checkers AI Backend", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    session = GameSession()

    def get_session() -> GameSession:
        return session

    @app.get("/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/board")
    def read_board(session: GameSession = Depends(get_session)):
        return session.serialize()

    @app.get("/valid-moves")
    def read_valid_moves(
        row: int = Query(..., ge=0),
        col: int = Query(..., ge=0),
        session: GameSession = Depends(get_session),
    ):
        try:
            return session.get_valid_moves(row, col)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/move")
    def play_move(payload: MoveRequest, session: GameSession = Depends(get_session)):
        try:
            return session.make_move(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/ai-move")
    def ai_move(payload: AIMoveRequest, session: GameSession = Depends(get_session)):
        try:
            return session.run_ai_move(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/ai-perform")
    def ai_perform(payload: PerformAIMoveRequest, session: GameSession = Depends(get_session)):
        try:
            return session.perform_ai_move(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/undo")
    def undo_move(session: GameSession = Depends(get_session)):
        try:
            return session.undo_move()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/reset")
    def reset_game(payload: Optional[ResetRequest] = None, session: GameSession = Depends(get_session)):
        return session.reset(payload)

    @app.post("/variant")
    def change_variant(payload: VariantRequest, session: GameSession = Depends(get_session)):
        return session.set_variant(payload)

    @app.post("/config")
    def configure_players(payload: ConfigRequest, session: GameSession = Depends(get_session)):
        try:
            return session.configure_players(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


app = create_app()
