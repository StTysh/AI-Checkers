from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import json
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
import os
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import secrets
import time
from threading import Lock

try:
    import msvcrt
except ImportError:  # pragma: no cover - Windows is the primary target, but keep a fallback.
    msvcrt = None

try:
    import fcntl
except ImportError:  # pragma: no cover - unavailable on Windows.
    fcntl = None

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
_DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _allowed_origins_from_env() -> list[str]:
    raw = os.getenv("CHECKERS_ALLOWED_ORIGINS")
    if not raw:
        return list(_DEFAULT_ALLOWED_ORIGINS)
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or list(_DEFAULT_ALLOWED_ORIGINS)


def _runtime_state_file() -> Path:
    configured = os.getenv("CHECKERS_STATE_FILE")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / ".runtime" / "session_store.json"


@contextmanager
def _locked_state_file(path: Path):
    lock_path = path.with_suffix(f"{path.suffix}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        if msvcrt is not None:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        elif fcntl is not None:  # pragma: no cover - Linux/macOS fallback
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield handle
        finally:
            if msvcrt is not None:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            elif fcntl is not None:  # pragma: no cover
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class _SessionStore:
    def __init__(
        self,
        *,
        max_sessions: int = 500,
        session_ttl_seconds: int = 7 * 24 * 60 * 60,
        state_file: Optional[Path] = None,
    ) -> None:
        self._lock = Lock()
        self._sessions: dict[str, GameSession] = {}
        self._last_access: dict[str, float] = {}
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._max_sessions = max(1, int(max_sessions))
        self._session_ttl_seconds = max(60, int(session_ttl_seconds))
        self._state_file = state_file or _runtime_state_file()
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def get_or_create(self, session_id: Optional[str]) -> tuple[str, GameSession, bool]:
        now = time.time()
        with self._lock:
            self._prune_expired_locked(now)
            if session_id:
                session = self._sessions.get(session_id)
                if session is not None:
                    self._last_access[session_id] = now
                    self._persist_locked()
                    return session_id, session, False
                self._load_locked()
                self._prune_expired_locked(now)
                session = self._sessions.get(session_id)
                if session is not None:
                    self._last_access[session_id] = now
                    self._persist_locked()
                    return session_id, session, False

            session_id = secrets.token_urlsafe(24)
            session = GameSession(on_change=self._make_on_change(session_id))
            self._sessions[session_id] = session
            self._last_access[session_id] = now
            self._snapshots[session_id] = session.snapshot()

            if len(self._sessions) > self._max_sessions:
                oldest = min(self._last_access.items(), key=lambda item: item[1])[0]
                self._sessions.pop(oldest, None)
                self._last_access.pop(oldest, None)
                self._snapshots.pop(oldest, None)

            self._persist_locked()
            return session_id, session, True

    def _make_on_change(self, session_id: str):
        def _on_change(snapshot: dict[str, Any]) -> None:
            with self._lock:
                self._snapshots[session_id] = snapshot
                self._last_access[session_id] = time.time()
                self._persist_locked()

        return _on_change

    def _prune_expired_locked(self, now: float) -> None:
        expired = [
            session_id
            for session_id, last_access in self._last_access.items()
            if now - last_access > self._session_ttl_seconds
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)
            self._last_access.pop(session_id, None)
            self._snapshots.pop(session_id, None)

    def _persist_locked(self) -> None:
        with _locked_state_file(self._state_file) as handle:
            persisted = self._read_state_locked()
            merged_sessions = persisted.get("sessions", {})
            for session_id in list(merged_sessions.keys()):
                last_access = float(merged_sessions[session_id].get("lastAccess", 0.0))
                if time.time() - last_access > self._session_ttl_seconds:
                    merged_sessions.pop(session_id, None)

            for session_id, snapshot in self._snapshots.items():
                local_record = {
                    "lastAccess": self._last_access.get(session_id, 0.0),
                    "snapshot": snapshot,
                }
                existing_record = merged_sessions.get(session_id)
                if existing_record is None or float(existing_record.get("lastAccess", 0.0)) <= local_record["lastAccess"]:
                    merged_sessions[session_id] = local_record

            payload = {"version": 1, "sessions": merged_sessions}
            self._write_state_locked(payload)

    def _load(self) -> None:
        with self._lock:
            self._load_locked()
            if self._sessions:
                self._persist_locked()

    def _load_locked(self) -> None:
        if not self._state_file.exists():
            return
        with _locked_state_file(self._state_file) as handle:
            payload = self._read_state_locked()

        now = time.time()
        sessions = payload.get("sessions", {})
        self._sessions.clear()
        self._last_access.clear()
        self._snapshots.clear()
        for session_id, record in sessions.items():
            last_access = float(record.get("lastAccess", now))
            if now - last_access > self._session_ttl_seconds:
                continue
            snapshot = record.get("snapshot")
            if not isinstance(snapshot, dict):
                continue
            session = GameSession.from_snapshot(snapshot, on_change=self._make_on_change(session_id))
            session.resume_pending_evaluations()
            self._sessions[session_id] = session
            self._last_access[session_id] = last_access
            self._snapshots[session_id] = snapshot
        if len(self._sessions) > self._max_sessions:
            for session_id in sorted(self._last_access, key=self._last_access.get)[:-self._max_sessions]:
                self._sessions.pop(session_id, None)
                self._last_access.pop(session_id, None)
                self._snapshots.pop(session_id, None)

    def _read_state_locked(self) -> dict[str, Any]:
        if not self._state_file.exists():
            return {"version": 1, "sessions": {}}
        try:
            return json.loads(self._state_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Session store file is corrupted or unreadable: {self._state_file}") from exc

    def _write_state_locked(self, payload: dict[str, Any]) -> None:
        temp_path = self._state_file.with_suffix(f"{self._state_file.suffix}.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, self._state_file)


def create_app() -> FastAPI:
    app = FastAPI(title="Checkers AI Backend", version="1.0.0")
    allowed_origins = _allowed_origins_from_env()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    store = _SessionStore(
        max_sessions=_int_env("CHECKERS_MAX_SESSIONS", 500),
        session_ttl_seconds=_int_env("CHECKERS_SESSION_TTL_SECONDS", 7 * 24 * 60 * 60),
        state_file=_runtime_state_file(),
    )
    app.state.session_store = store

    def get_session(request: Request, response: Response) -> GameSession:
        session_id = request.cookies.get(_SESSION_COOKIE_NAME)
        session_id, session, created = store.get_or_create(session_id)
        if created:
            secure_cookie = _bool_env("CHECKERS_COOKIE_SECURE", request.url.scheme == "https")
            response.set_cookie(
                _SESSION_COOKIE_NAME,
                session_id,
                httponly=True,
                samesite="lax",
                secure=secure_cookie,
                path="/",
                max_age=_int_env("CHECKERS_SESSION_TTL_SECONDS", 7 * 24 * 60 * 60),
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
