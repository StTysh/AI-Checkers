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


class PlayerConfigPayload(BaseModel):
    type: Optional[
        Literal["human", "minimax", "mcts", "genetic", "reinforcement", "remote"]
    ] = None
    depth: Optional[int] = Field(default=None, ge=1, le=16)
    alphaBeta: Optional[bool] = None
    transposition: Optional[bool] = None
    moveOrdering: Optional[bool] = None
    iterativeDeepening: Optional[bool] = None
    quiescence: Optional[bool] = None


class ConfigRequest(BaseModel):
    white: Optional[PlayerConfigPayload] = None
    black: Optional[PlayerConfigPayload] = None


class VariantRequest(BaseModel):
    variant: Literal["british", "international"]


class ResetRequest(BaseModel):
    variant: Optional[Literal["british", "international"]] = None


class AIMoveRequest(BaseModel):
    color: Optional[Literal["white", "black"]] = None
    algorithm: Literal["minimax"] = "minimax"
    depth: Optional[int] = Field(default=None, ge=1, le=16)
    persist: bool = True
