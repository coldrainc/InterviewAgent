"""生产环境初始化：把 demos 里 Scenario yml 批量导入 Mongo；也支持 CLI。
用法：
  poetry run python -m app.scripts.seed_scenarios path/to/scenarios/*.yml
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


async def _seed(files: list[str]):
    from app.config import get_settings
    from app.models.mongo import (
        AnalyzerFindingDoc, AuditLogDoc, BaselineDoc, RunDoc, ScenarioDoc, SpanDoc,
    )
    from app.schema import Scenario

    s = get_settings()
    cli = AsyncIOMotorClient(s.MONGO_URI.get_secret_value())
    await init_beanie(
        database=getattr(cli, s.MONGO_DB_NAME),
        document_models=[ScenarioDoc, RunDoc, SpanDoc, BaselineDoc,
                         AnalyzerFindingDoc, AuditLogDoc],
    )
    for f in files:
        payload = Scenario.load(f)
        existing = await ScenarioDoc.find_one(
            {"scenario_id": payload.scenario_id, "version": payload.version})
        if existing:
            print(f"[skip] {payload.scenario_id} v{payload.version} exists")
            continue
        doc = ScenarioDoc(**payload.model_dump())
        doc.created_by = doc.updated_by = "seed_script"
        await doc.insert()
        print(f"[ok] imported {payload.scenario_id} version={payload.version}")


def main():
    files = [a for a in sys.argv[1:] if Path(a).exists()]
    if not files:
        default = Path(__file__).resolve().parents[4] / "workflow-harness" / "scenarios"
        if default.exists():
            files = list(default.glob("*.yml"))
    if not files:
        print("用法：python -m app.scripts.seed_scenarios <file1.yml> [file2.yml ...]")
        raise SystemExit(1)
    asyncio.run(_seed([str(f) for f in files]))


if __name__ == "__main__":
    main()
