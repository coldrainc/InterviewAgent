from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "tests" / ".runtime"


def configure_environment() -> int:
    shutil.rmtree(RUNTIME, ignore_errors=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    database = RUNTIME / "e2e.sqlite3"
    codex_home = RUNTIME / "codex-home"
    codex_home.mkdir(parents=True, exist_ok=True)
    api_port = int(os.getenv("E2E_API_PORT", "18020"))
    web_port = int(os.getenv("E2E_WEB_PORT", "15175"))
    values = {
        "INTERVIEW_ENV": "test",
        "DATABASE_URL": f"sqlite+aiosqlite:///{database}",
        "INTERVIEW_STORAGE_BACKEND": "database",
        "INTERVIEW_OBJECT_STORAGE_BACKEND": "local",
        "INTERVIEW_VECTOR_STORE": "json",
        "EMBEDDING_PROVIDER": "disabled",
        "CODEX_HOME": str(codex_home),
        "OPENAI_API_KEY": "",
        "GATEWAY_API_KEY": "",
        "ARK_API_KEY": "",
        "INTERVIEW_API_AUTH_REQUIRED": "true",
        "INTERVIEW_AUTH_TOKEN_SECRET": "isolated-e2e-secret-not-for-production",
        "INTERVIEW_AUTH_DEV_LOGIN_ENABLED": "false",
        "INTERVIEW_AUTH_MOCK_PROVIDER_LOGIN_ENABLED": "false",
        "INTERVIEW_ALLOW_MOCK_RECHARGE": "false",
        "INTERVIEW_RATE_LIMIT_PER_MINUTE": "0",
        "INTERVIEW_TRIAL_USES": "100",
        "INTERVIEW_ALLOWED_ORIGINS": f"http://127.0.0.1:{web_port}",
        "INTERVIEW_KNOWLEDGE_BASE": str(ROOT / "knowledge_base/ai-interview-guide/docs"),
        "INTERVIEW_RAG_INDEX": str(RUNTIME / "rag_index.json"),
        "INTERVIEW_RAG_VECTORS": str(RUNTIME / "rag_vectors.json"),
        "INTERVIEW_VECTOR_STORE_METADATA": str(RUNTIME / "vector_store.json"),
        "INTERVIEW_MEMORY_PATH": str(RUNTIME / "memory"),
        "INTERVIEW_SECURITY_ALERT_LOG": str(RUNTIME / "security_alerts.log"),
    }
    os.environ.update(values)
    os.chdir(RUNTIME)
    sys.path.insert(0, str(ROOT / "backend/src"))
    return api_port


if __name__ == "__main__":
    import uvicorn

    port = configure_environment()
    from interview_agent.interfaces.api import create_app

    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")
