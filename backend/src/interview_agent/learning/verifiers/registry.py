from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.learning.projector import infer_task_type
from interview_agent.learning.verifiers.interview import InterviewTaskVerifier
from interview_agent.learning.verifiers.practice import PracticeTaskVerifier
from interview_agent.learning.verifiers.self_attested import SelfAttestedTaskVerifier


def verifier_for(task, session: AsyncSession, *, tenant_id: str, user_id: str):
    task_type = infer_task_type(
        link_type=task.link_type,
        simulation=bool(task.simulation),
        source=task.source,
    )
    if task_type == "interview":
        return InterviewTaskVerifier(session, tenant_id=tenant_id, user_id=user_id)
    if task_type == "practice":
        return PracticeTaskVerifier(session, tenant_id=tenant_id, user_id=user_id)
    return SelfAttestedTaskVerifier()
