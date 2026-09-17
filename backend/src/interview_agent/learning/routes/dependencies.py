from fastapi import HTTPException

from interview_agent.infrastructure.security import RequestContext


def require_authenticated(context: RequestContext) -> None:
    if not context.authenticated:
        raise HTTPException(status_code=401, detail="请先登录。")
