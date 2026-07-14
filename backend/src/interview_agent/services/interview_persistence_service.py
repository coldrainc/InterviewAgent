from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.core.config import InterviewConfig
from interview_agent.core.state import InterviewState
from interview_agent.infrastructure.conversation_store import ConversationStore
from interview_agent.repositories.interview_repository import InterviewRepository


class InterviewPersistenceService:
    def __init__(
        self,
        session: AsyncSession,
        tenant_id: str = "default",
        user_id: str = "anonymous",
        export_markdown: bool = True,
        export_root: Path = Path(".interview_agent/conversations"),
        memory_root: Path = Path(".interview_agent/memory"),
    ) -> None:
        self.repository = InterviewRepository(session, tenant_id=tenant_id, user_id=user_id)
        self.export_markdown = export_markdown
        self.export_root = export_root
        self.memory_root = memory_root

    async def create_session(
        self,
        *,
        session_id: str,
        config: InterviewConfig,
        state: InterviewState,
        resume_id: str | None = None,
    ) -> None:
        await self.repository.create_session(
            session_id=session_id,
            config=config,
            state=state,
            resume_id=resume_id,
        )
        if self.export_markdown:
            self._export(session_id, config, state)

    async def persist_turn(
        self,
        *,
        session_id: str,
        config: InterviewConfig,
        state: InterviewState,
        event_type: str,
        message: str,
        advanced: bool,
        fallback_used: bool,
        guardrails: list[str],
    ) -> None:
        await self.repository.sync_session_state(
            session_id=session_id,
            config=config,
            state=state,
            fallback_used=fallback_used,
            guardrails=guardrails,
        )
        if self.export_markdown:
            store = self._store_for_session(session_id)
            store.record_event(
                event_type,
                {
                    "message": message,
                    "advanced": advanced,
                    "fallback_used": fallback_used,
                    "stage": state.stage.value,
                    "guardrails": guardrails,
                },
            )
            store.save_state(config, state)

    async def get_session_record(self, session_id: str) -> dict | None:
        return await self.repository.get_session_record(session_id)

    async def list_sessions(self, limit: int = 50) -> list[dict]:
        return await self.repository.list_sessions(limit=limit)

    async def delete_session(self, session_id: str) -> bool:
        return await self.repository.delete_session(session_id)

    def _export(self, session_id: str, config: InterviewConfig, state: InterviewState) -> None:
        self._store_for_session(session_id).save_state(config, state)

    def _store_for_session(self, session_id: str) -> ConversationStore:
        store = ConversationStore(root=self.export_root, memory_root=self.memory_root)
        store.session_id = session_id
        store.jsonl_path = self.export_root / f"{session_id}.jsonl"
        store.markdown_path = self.export_root / f"{session_id}.md"
        store.memory_path = self.memory_root / f"{session_id}.md"
        return store
