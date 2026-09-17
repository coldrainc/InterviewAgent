from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LearningTaskCommandRequest(BaseModel):
    action: str = Field(pattern="^(start|complete|reopen|verify)$")
    expected_version: int | None = Field(default=None, ge=0)
    elapsed_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    mastery_score: int | None = Field(default=None, ge=0, le=5)
    note: str | None = Field(default=None, max_length=2000)
    evidence: dict[str, Any] = Field(default_factory=dict)


class LearningGoalRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    target_role: str = Field(default="", max_length=255)
    deadline: str | None = None
    daily_minutes: int = Field(default=30, ge=10, le=12 * 60)
    success_criteria: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    expected_version: int | None = Field(default=None, ge=1)


class RevisionDecisionRequest(BaseModel):
    action: str = Field(pattern="^(apply|revert)$")
