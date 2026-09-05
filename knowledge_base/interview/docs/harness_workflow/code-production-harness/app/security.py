"""鉴权：JWT + OIDC SSO；RBAC：基于 policy 文件；审计日志。"""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Callable, Optional

import structlog
from fastapi import Depends, HTTPException, Request, status
from jose import ExpiredSignatureError, JWTError, jwt
from pydantic import BaseModel, Field

from .config import get_settings

logger = structlog.get_logger()


class User(BaseModel):
    sub: str
    email: str = ""
    roles: list[str] = Field(default_factory=list)  # admin/platform/dev/viewer/ci

    def has_role(self, required: str) -> bool:
        return required in self.roles or "admin" in self.roles


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def create_access_token(user: User) -> str:
    s = get_settings()
    expire = datetime.utcnow() + timedelta(minutes=s.JWT_EXPIRE_MIN)
    payload = {
        "sub": user.sub, "email": user.email,
        "roles": user.roles, "exp": expire,
    }
    return jwt.encode(payload, s.JWT_SECRET.get_secret_value(), algorithm=s.JWT_ALG)


def _decode_token(token: str) -> dict[str, Any]:
    try:
        s = get_settings()
        return jwt.decode(token, s.JWT_SECRET.get_secret_value(),
                          algorithms=[s.JWT_ALG])
    except ExpiredSignatureError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token 已过期") from e
    except JWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token 非法") from e


async def current_user(request: Request) -> User:
    """FastAPI Depends 注入当前用户。"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        # 允许 CI 使用内部 token（X-Harness-CI-Token，与 JWT_SECRET 派生）
        ci = request.headers.get("X-Harness-CI-Token")
        s = get_settings()
        if ci and ci == s.JWT_SECRET.get_secret_value()[:32]:
            return User(sub="ci-service", email="ci@internal", roles=["ci", "viewer"])
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "缺少 Authorization")
    data = _decode_token(auth[7:])
    return User(sub=data["sub"], email=data.get("email", ""), roles=data.get("roles", []))


# ---------------------------------------------------------------------------
# RBAC：基于 policy 文件声明每个 API 所需角色
# rbac_policy.yml 示例：
#   scenarios:
#     create: [admin, platform, dev]
#     read:   [admin, platform, dev, viewer, ci]
#   runs:
#     trigger: [admin, platform, dev, ci]
#     read:    [admin, platform, dev, viewer, ci]
#   baselines:
#     update: [admin, platform]
# ---------------------------------------------------------------------------

import yaml
from pathlib import Path

@lru_cache(maxsize=1)
def _load_policy() -> dict[str, dict[str, list[str]]]:
    path = Path(get_settings().RBAC_POLICY_FILE)
    if not path.exists():
        # 默认策略，避免生产启动因缺文件失败
        return {
            "scenarios": {"write": ["admin", "platform", "dev"], "read": ["*"]},
            "runs":      {"trigger": ["admin", "platform", "dev", "ci"], "read": ["*"]},
            "baselines": {"update": ["admin", "platform"], "read": ["*"]},
            "admin":     {"*": ["admin"]},
        }
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def require(resource: str, action: str) -> Callable[..., User]:
    """生成 Depends：校验登录 + 角色。
    用法：@app.post(..., dependencies=[Depends(require("scenarios", "write"))])
    """
    def _dep(user: User = Depends(current_user)) -> User:
        policy = _load_policy()
        rules = policy.get(resource, {}).get(action) or policy.get(resource, {}).get("*", [])
        if "*" in rules or any(user.has_role(r) for r in rules):
            return user
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"需要角色之一 {rules}，你的角色 {user.roles}")
    return _dep


# ---------------------------------------------------------------------------
# 审计日志中间件（写操作）
# ---------------------------------------------------------------------------

async def audit_logging(request: Request, call_next):
    # 仅对写方法记审计
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        start = datetime.utcnow()
        resp = await call_next(request)
        try:
            user = getattr(request.state, "user", None)
            if user is not None:
                diff: dict[str, Any] = {"path": request.url.path, "status": resp.status_code}
                # 轻量审计：详情存 Mongo（此处仅示例；实际由各 endpoint 显式写更精准）
                from .models.mongo import AuditLogDoc
                await AuditLogDoc(
                    user=user.sub, action=request.method, resource=request.url.path.split("/")[2],
                    ip=request.client.host if request.client else None,
                    diff=diff, created_at=start,
                ).insert()
        except Exception as e:  # pragma: no cover - 防御，不影响业务
            logger.warning("audit_write_failed", err=str(e))
        return resp
    return await call_next(request)
