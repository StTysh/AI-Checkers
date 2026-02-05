from __future__ import annotations

from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
import os
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import secrets
import time
from threading import Lock

from .schemas import (
    AIMoveRequest,
    ConfigRequest,
    MoveRequest,
    PerformAIMoveRequest,
    ResetRequest,
    VariantRequest,
    EvaluationStartRequest,
    EvaluationStopRequest,
)
from .session import GameSession


_SESSION_COOKIE_NAME = "checkers_session_id"


class _SessionStore:
    def __init__(self, *, max_sessions: int = 500) -> None:
        self._lock = Lock()
        self._sessions: dict[str, GameSession] = {}
        self._last_access: dict[str, float] = {}
        self._max_sessions = max(1, int(max_sessions))

    def get_or_create(self, session_id: Optional[str]) -> tuple[str, GameSession, bool]:
        now = time.time()
        with self._lock:
            if session_id:
                session = self._sessions.get(session_id)
                if session is not None:
                    self._last_access[session_id] = now
                    return session_id, session, False

            session_id = secrets.token_urlsafe(24)
            session = GameSession()
            self._sessions[session_id] = session
            self._last_access[session_id] = now

            if len(self._sessions) > self._max_sessions:
                oldest = min(self._last_access.items(), key=lambda item: item[1])[0]
                self._sessions.pop(oldest, None)
                self._last_access.pop(oldest, None)

            return session_id, session, True


def create_app() -> FastAPI:
    app = FastAPI(title="Checkers AI Backend", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    store = _SessionStore()

    def get_session(request: Request, response: Response) -> GameSession:
        session_id = request.cookies.get(_SESSION_COOKIE_NAME)
        session_id, session, created = store.get_or_create(session_id)
        if created:
            response.set_cookie(
                _SESSION_COOKIE_NAME,
                session_id,
                httponly=True,
                samesite="lax",
                path="/",
            )
        return session

    @app.get("/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/board")
    def read_board(session: GameSession = Depends(get_session)):
        return session.serialize()

    @app.get("/system-info")
    def system_info():
        cpu_total = os.cpu_count() or 1
        recommended_max = max(1, cpu_total - 2)
        return {"cpuCount": cpu_total, "recommendedMaxWorkers": recommended_max}

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

    @app.post("/evaluate/start")
    def evaluate_start(payload: EvaluationStartRequest, session: GameSession = Depends(get_session)):
        try:
            return session.start_evaluation(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/evaluate/status")
    def evaluate_status(evaluation_id: str = Query(..., alias="evaluation_id"), session: GameSession = Depends(get_session)):
        try:
            return session.get_evaluation_status(evaluation_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/evaluate/stop")
    def evaluate_stop(payload: EvaluationStopRequest, session: GameSession = Depends(get_session)):
        try:
            return session.stop_evaluation(payload)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/evaluate/results")
    def evaluate_results(
        evaluation_id: str = Query(..., alias="evaluation_id"),
        format: str = Query("csv", pattern="^(csv|json)$"),
        session: GameSession = Depends(get_session),
    ):
        try:
            content_type, payload = session.get_evaluation_results(evaluation_id, format)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if content_type == "application/json":
            return payload
        return Response(content=payload, media_type=content_type)

    return app


app = create_app()
