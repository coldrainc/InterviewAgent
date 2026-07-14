from __future__ import annotations

from pydantic import BaseModel, Field

from interview_agent.core.config import InterviewStage


class InterviewTurn(BaseModel):
    stage: InterviewStage
    interviewer: str
    candidate: str | None = None


class InterviewState(BaseModel):
    stage: InterviewStage = InterviewStage.INTRO
    turns: list[InterviewTurn] = Field(default_factory=list)
    current_focus_index: int = 0
    focus_followup_count: int = 0
    last_answer_assessment: str = ""
    completed: bool = False

    def transcript(self) -> str:
        lines: list[str] = []
        for index, turn in enumerate(self.turns, start=1):
            lines.append(f"Turn {index} [{turn.stage.value}]")
            lines.append(f"面试官：{turn.interviewer}")
            if turn.candidate:
                lines.append(f"候选人：{turn.candidate}")
        return "\n".join(lines).strip()

    def add_interviewer_message(self, stage: InterviewStage, content: str) -> None:
        self.turns.append(InterviewTurn(stage=stage, interviewer=content))

    def add_candidate_message(self, content: str) -> None:
        if not self.turns:
            raise ValueError("Cannot add a candidate response before an interviewer turn.")
        self.turns[-1].candidate = content
