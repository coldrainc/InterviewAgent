from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.core.config import InterviewConfig
from interview_agent.core.state import InterviewState
from interview_agent.infrastructure.db.models import (
    InterviewSessionModel,
    InterviewTurnModel,
    MemoryItemModel,
)


class InterviewRepository:
    def __init__(self, session: AsyncSession, tenant_id: str = "default", user_id: str = "anonymous") -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def create_session(
        self,
        *,
        session_id: str,
        config: InterviewConfig,
        state: InterviewState,
        resume_id: str | None = None,
    ) -> None:
        candidate = config.candidate
        model = InterviewSessionModel(
            id=uuid.UUID(session_id),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            resume_id=uuid.UUID(resume_id) if resume_id else None,
            mode=config.mode.value,
            industry=config.industry.value,
            candidate_name=candidate.name,
            target_role=candidate.target_role,
            seniority=candidate.seniority,
            config_json=config.model_dump(mode="json"),
            state_json=state.model_dump(mode="json"),
            status="completed" if state.completed else "active",
        )
        self.session.add(model)
        await self.session.flush()

    async def sync_session_state(
        self,
        *,
        session_id: str,
        config: InterviewConfig,
        state: InterviewState,
        fallback_used: bool = False,
        guardrails: list[str] | None = None,
    ) -> None:
        model = await self.session.get(InterviewSessionModel, uuid.UUID(session_id))
        if model is None or model.tenant_id != self.tenant_id or model.user_id != self.user_id:
            await self.create_session(session_id=session_id, config=config, state=state)
            model = await self.session.get(InterviewSessionModel, uuid.UUID(session_id))
        if model is None:
            raise ValueError("failed to create interview session")

        model.state_json = state.model_dump(mode="json")
        model.config_json = config.model_dump(mode="json")
        model.status = "completed" if state.completed else "active"

        await self.session.execute(
            delete(MemoryItemModel).where(MemoryItemModel.session_id == model.id)
        )
        await self.session.execute(
            delete(InterviewTurnModel).where(InterviewTurnModel.session_id == model.id)
        )
        await self.session.flush()

        for index, turn in enumerate(state.turns, start=1):
            turn_model = InterviewTurnModel(
                session_id=model.id,
                turn_index=index,
                stage=turn.stage.value,
                interviewer=turn.interviewer,
                candidate=turn.candidate,
                assessment=state.last_answer_assessment if index == len(state.turns) else None,
                guardrails_json=guardrails or [],
                fallback_used=fallback_used if index == len(state.turns) else False,
            )
            self.session.add(turn_model)
            await self.session.flush()
            if turn.candidate:
                memory = build_memory_payload(config, turn.stage.value, turn.interviewer, turn.candidate)
                if memory:
                    self.session.add(
                        MemoryItemModel(
                            tenant_id=self.tenant_id,
                            user_id=self.user_id,
                            session_id=model.id,
                            turn_id=turn_model.id,
                            kind="interview_qa",
                            content=memory["content"],
                            reason=memory["reason"],
                            metadata_json=memory["metadata"],
                        )
                    )
        await self.session.flush()

    async def get_state_json(self, session_id: str) -> dict | None:
        model = await self.session.get(InterviewSessionModel, uuid.UUID(session_id))
        if model is None or model.tenant_id != self.tenant_id or model.user_id != self.user_id:
            return None
        return model.state_json

    async def get_session_record(self, session_id: str) -> dict | None:
        result = await self.session.execute(
            select(InterviewSessionModel)
            .options(selectinload(InterviewSessionModel.turns))
            .where(
                InterviewSessionModel.id == uuid.UUID(session_id),
                InterviewSessionModel.tenant_id == self.tenant_id,
                InterviewSessionModel.user_id == self.user_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return _session_to_dict(model)

    async def list_sessions(self, limit: int = 50) -> list[dict]:
        result = await self.session.execute(
            select(InterviewSessionModel)
            .where(
                InterviewSessionModel.tenant_id == self.tenant_id,
                InterviewSessionModel.user_id == self.user_id,
            )
            .order_by(InterviewSessionModel.updated_at.desc())
            .limit(limit)
        )
        return [_session_to_summary(model) for model in result.scalars().all()]

    async def delete_session(self, session_id: str) -> bool:
        model = await self.session.get(InterviewSessionModel, uuid.UUID(session_id))
        if model is None or model.tenant_id != self.tenant_id or model.user_id != self.user_id:
            return False
        await self.session.delete(model)
        await self.session.flush()
        return True

    async def list_memory(self, limit: int = 200) -> list[str]:
        result = await self.session.execute(
            select(MemoryItemModel.content)
            .where(MemoryItemModel.tenant_id == self.tenant_id, MemoryItemModel.user_id == self.user_id)
            .order_by(MemoryItemModel.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


def _session_to_summary(model: InterviewSessionModel) -> dict:
    return {
        "id": str(model.id),
        "resume_id": str(model.resume_id) if model.resume_id else None,
        "mode": model.mode,
        "industry": model.industry,
        "candidate_name": model.candidate_name,
        "target_role": model.target_role,
        "seniority": model.seniority,
        "status": model.status,
        "created_at": model.created_at.isoformat(),
        "updated_at": model.updated_at.isoformat(),
    }


def _session_to_dict(model: InterviewSessionModel) -> dict:
    payload = _session_to_summary(model)
    payload["config"] = model.config_json
    payload["state"] = model.state_json
    payload["turns"] = [
        {
            "id": str(turn.id),
            "turn_index": turn.turn_index,
            "stage": turn.stage,
            "interviewer": turn.interviewer,
            "candidate": turn.candidate,
            "assessment": turn.assessment,
            "guardrails": turn.guardrails_json,
            "fallback_used": turn.fallback_used,
            "created_at": turn.created_at.isoformat(),
            "updated_at": turn.updated_at.isoformat(),
        }
        for turn in sorted(model.turns, key=lambda item: item.turn_index)
    ]
    return payload


def build_memory_payload(
    config: InterviewConfig,
    stage: str,
    interviewer: str,
    candidate: str,
) -> dict | None:
    from interview_agent.core.state import InterviewTurn
    from interview_agent.infrastructure.conversation_store import memory_decision
    from interview_agent.core.config import InterviewStage

    turn = InterviewTurn(
        stage=InterviewStage(stage),
        interviewer=interviewer,
        candidate=candidate,
    )
    decision = memory_decision(turn)
    if not decision.keep:
        return None
    content = "\n".join(
        [
            "历史面试问答",
            f"候选人：{config.candidate.name}",
            f"岗位：{config.candidate.target_role}",
            f"阶段：{stage}",
            f"面试官问题：{interviewer}",
            f"候选人回答：{candidate}",
        ]
    )
    return {
        "content": content,
        "reason": decision.reason,
        "metadata": {
            "stage": stage,
            "target_role": config.candidate.target_role,
            "candidate_name": config.candidate.name,
            "type": "历史面试问答",
        },
    }
