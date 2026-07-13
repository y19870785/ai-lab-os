"""经验知识和决策知识数据模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from knowledge.models import AccessLevel


# ── 经验知识 ──


class ExperienceStep(BaseModel):
    """经验步骤。"""
    order: int
    description: str
    tools_needed: list[str] = []
    expected_duration: str | None = None
    tips: str | None = None


class ExperientialKnowledge(BaseModel):
    """经验知识。如何完成特定任务的实践知识。"""
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    title: str
    domain: str = ""

    context: str = ""
    steps: list[ExperienceStep] = []
    prerequisites: list[str] = []
    expected_outcome: str = ""

    derived_from: list[str] = []
    confidence: float = 0.5
    tags: list[str] = []

    access_level: AccessLevel = AccessLevel.PRIVATE
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ── 决策知识 ──


class DecisionAlternative(BaseModel):
    """决策备选方案。"""
    name: str
    description: str
    pros: list[str] = []
    cons: list[str] = []
    estimated_effort: str | None = None


class DecisionKnowledge(BaseModel):
    """决策知识。记录决策的上下文、选项、推理和结果。"""
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    title: str
    decision_type: str = ""

    context: str = ""
    alternatives: list[DecisionAlternative] = []
    chosen: str = ""
    reasoning: str = ""

    outcome: str | None = None
    outcome_notes: str | None = None
    lessons: str | None = None

    related_entities: list[str] = []
    related_documents: list[str] = []
    tags: list[str] = []

    access_level: AccessLevel = AccessLevel.PRIVATE
    decision_maker: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
