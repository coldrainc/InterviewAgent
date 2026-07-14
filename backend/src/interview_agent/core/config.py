from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from interview_agent.domain.billing import DEFAULT_CHAT_MODEL
from interview_agent.core.industry import (
    INDUSTRY_LABELS,
    Industry,
    get_industry_profile,
    recommended_focus_areas,
)


class InterviewStage(str, Enum):
    INTRO = "intro"
    QUESTIONING = "questioning"
    FOLLOW_UP = "follow_up"
    EVALUATION = "evaluation"
    COMPLETE = "complete"


class InterviewMode(str, Enum):
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"


class CandidateProfile(BaseModel):
    name: str = "候选人"
    target_role: str = "AI 应用工程师"
    seniority: str = "中级"
    resume_summary: str = "暂未提供简历摘要。"
    resume_text: str = ""
    project_experience: str = ""
    interview_goal: str = "围绕候选人的简历和 AI 工程经历进行技术深挖。"


class InterviewConfig(BaseModel):
    candidate: CandidateProfile = Field(default_factory=CandidateProfile)
    mode: InterviewMode = InterviewMode.INTERVIEWER
    industry: Industry = Industry.INTERNET
    focus_areas: list[str] = Field(
        default_factory=lambda: ["简历项目深挖", "AI 工程与 RAG/Agent", "系统设计与生产化", "行为协作能力"]
    )
    max_turns: int = 8
    questions_per_area: int = 1
    max_followups_per_focus: int = 3
    model_id: str = DEFAULT_CHAT_MODEL
    rubric: dict[str, str] = Field(
        default_factory=lambda: {
            "technical_depth": "答案正确性、技术取舍和解释深度。",
            "communication": "表达是否清晰、有结构，是否能主动澄清问题。",
            "problem_solving": "拆解问题、说明假设和迭代方案的能力。",
            "role_fit": "是否体现与目标岗位和级别匹配的证据。",
            "resume_truthfulness": "简历经历是否经得起细节追问，是否能讲出真实参与、难点和结果。",
            "ai_engineering": "是否理解 RAG、Agent、评测、安全、观测和生产化取舍。",
        }
    )

    @classmethod
    def from_json_file(cls, path: Path) -> "InterviewConfig":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def to_prompt_context(self) -> dict[str, Any]:
        industry_profile = get_industry_profile(self.industry)
        return {
            "candidate_name": self.candidate.name,
            "target_role": self.candidate.target_role,
            "seniority": self.candidate.seniority,
            "resume_summary": self.candidate.resume_summary,
            "resume_text": self.candidate.resume_text or "暂未提供完整简历。",
            "project_experience": self.candidate.project_experience or "暂未提供做过的事情。",
            "interview_goal": self.candidate.interview_goal,
            "mode": self.mode.value,
            "mode_label": "Agent 作为面试官" if self.mode == InterviewMode.INTERVIEWER else "Agent 作为被面试候选人",
            "industry": self.industry.value,
            "industry_label": INDUSTRY_LABELS.get(self.industry, self.industry.value),
            "industry_profile": industry_profile.to_prompt_block(),
            "industry_keywords": "、".join(industry_profile.scenario_keywords),
            "industry_focus": "、".join(industry_profile.interview_focus),
            "industry_signals": "、".join(industry_profile.production_signals),
            "industry_risks": "、".join(industry_profile.risk_controls),
            "recommended_focus_areas": "、".join(
                recommended_focus_areas(self.industry, self.candidate.target_role)
            ),
            "focus_areas": "、".join(self.focus_areas),
            "rubric": "\n".join(f"- {key}: {value}" for key, value in self.rubric.items()),
            "questions_per_area": self.questions_per_area,
        }
