from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CandidateTextInput(BaseModel):
    type: Literal["input_text"]
    role: Literal["system", "user"]
    text: str


class CandidateImageInput(BaseModel):
    type: Literal["input_image"]
    role: Literal["current", "baseline", "overlay"]
    image_ref: str


class CandidateRequestPayload(BaseModel):
    model_version: str
    asset_id: str
    scenario_id: str
    inputs: list[CandidateTextInput | CandidateImageInput]


class CandidateResponsePayload(BaseModel):
    output_text: str
