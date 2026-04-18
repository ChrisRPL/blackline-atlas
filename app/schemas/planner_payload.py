from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class PlannerTextInput(BaseModel):
    type: Literal["input_text"]
    role: Literal["system", "user"]
    text: str


class PlannerRequestPayload(BaseModel):
    model_version: str
    inputs: list[PlannerTextInput]


class PlannerResponsePayload(BaseModel):
    output_text: str
