from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class CoordinateModel(BaseModel):
    row: int = Field(..., ge=0)
    col: int = Field(..., ge=0)


class MoveRequest(BaseModel):
    start: CoordinateModel
    steps: list[CoordinateModel] = Field(
        ..., min_length=1, description="Ordered path after the starting square."
    )


class AIConfigFields(BaseModel):
    depth: Optional[int] = Field(default=None, ge=1, le=16)
    alphaBeta: Optional[bool] = None
    transposition: Optional[bool] = None
    moveOrdering: Optional[bool] = None
    killerMoves: Optional[bool] = None
    iterativeDeepening: Optional[bool] = None
    quiescence: Optional[bool] = None
    maxQuiescenceDepth: Optional[int] = Field(default=None, ge=1, le=16)
    aspiration: Optional[bool] = None
    aspirationWindow: Optional[float] = Field(default=None, ge=10.0, le=200.0)
    historyHeuristic: Optional[bool] = None
    butterflyHeuristic: Optional[bool] = None
    nullMove: Optional[bool] = None
    nullMoveReduction: Optional[int] = Field(default=None, ge=1, le=4)
    lmr: Optional[bool] = None
    lmrMinDepth: Optional[int] = Field(default=None, ge=1, le=10)
    lmrMinMoves: Optional[int] = Field(default=None, ge=1, le=12)
    lmrReduction: Optional[int] = Field(default=None, ge=1, le=3)
    deterministicOrdering: Optional[bool] = None
    endgameTablebase: Optional[bool] = None
    endgameMaxPieces: Optional[int] = Field(default=None, ge=2, le=12)
    endgameMaxPlies: Optional[int] = Field(default=None, ge=4, le=200)
    timeLimitMs: Optional[int] = Field(default=None, ge=10, le=60000)
    parallel: Optional[bool] = None
    workers: Optional[int] = Field(default=None, ge=1, le=64)
    iterations: Optional[int] = Field(default=None, ge=1, le=20000)
    rolloutDepth: Optional[int] = Field(default=None, ge=1, le=300)
    explorationConstant: Optional[float] = Field(default=None, ge=0.01, le=10.0)
    randomSeed: Optional[int] = None
    mctsParallel: Optional[bool] = None
    mctsWorkers: Optional[int] = Field(default=None, ge=1, le=64)
    rolloutPolicy: Optional[Literal["random", "heuristic", "minimax_guided"]] = None
    guidanceDepth: Optional[int] = Field(default=None, ge=1, le=4)
    rolloutCutoffDepth: Optional[int] = Field(default=None, ge=1, le=300)
    leafEvaluation: Optional[Literal["random_terminal", "heuristic_eval", "minimax_eval"]] = None
    mctsTransposition: Optional[bool] = None
    mctsTranspositionMaxEntries: Optional[int] = Field(default=None, ge=1000, le=1_000_000)
    progressiveWidening: Optional[bool] = None
    pwK: Optional[float] = Field(default=None, ge=0.1, le=10.0)
    pwAlpha: Optional[float] = Field(default=None, ge=0.1, le=1.0)


class PlayerConfigPayload(AIConfigFields):
    type: Optional[
        Literal["human", "minimax", "mcts", "genetic", "reinforcement", "remote"]
    ] = None


class ConfigRequest(BaseModel):
    white: Optional[PlayerConfigPayload] = None
    black: Optional[PlayerConfigPayload] = None


class VariantRequest(BaseModel):
    variant: Literal["british", "international"]


class ResetRequest(BaseModel):
    variant: Optional[Literal["british", "international"]] = None


class AIMoveRequest(AIConfigFields):
    color: Optional[Literal["white", "black"]] = None
    algorithm: Literal["minimax", "mcts"] = "minimax"
    persist: bool = True
    commitImmediately: bool = True


class PerformAIMoveRequest(BaseModel):
    color: Literal["white", "black"]


class EvaluationStartRequest(BaseModel):
    games: int = Field(..., ge=1, le=500)
    variant: Literal["british", "international"]
    startPolicy: Literal["alternate", "white", "black"] = "alternate"
    randomSeed: Optional[int] = None
    randomizeOpening: bool = False
    randomizePlies: int = Field(default=0, ge=0, le=12)
    resetConfigsAfterRun: bool = False
    experimentName: Optional[str] = None
    notes: Optional[str] = None
    drawPolicy: Optional[Literal["zero", "half", "ignore"]] = "half"
    white: PlayerConfigPayload
    black: PlayerConfigPayload


class EvaluationStopRequest(BaseModel):
    evaluationId: str
