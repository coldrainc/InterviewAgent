"""一次性迁移脚本：civil_service_questions (v1) -> practice_questions (v2)。

用法：
    ../.venv/bin/python scripts/migrate_civil_service_to_practice.py [--dry-run] [--database-url URL]

--dry-run 只统计不提交。重复执行幂等（content_hash 去重）。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy.ext.asyncio import async_sessionmaker

from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.services.civil_service_migration import migrate_civil_service_questions


async def main() -> int:
    parser = argparse.ArgumentParser(description="迁移 v1 公考题库到 v2 practice_questions")
    parser.add_argument("--dry-run", action="store_true", help="只统计不提交")
    parser.add_argument("--database-url", default=None, help="覆盖默认数据库连接串")
    args = parser.parse_args()

    engine = create_engine_for_url(args.database_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with factory() as session:
            stats = await migrate_civil_service_questions(session)
            if args.dry_run:
                await session.rollback()
                print(f"[dry-run] 扫描 {stats['scanned']} 道 v1 题目，"
                      f"预计新建 {stats['created']}、更新 {stats['updated']}（{stats['owners']} 个用户空间）。")
            else:
                await session.commit()
                print(f"迁移完成：扫描 {stats['scanned']} 道，新建 {stats['created']}，"
                      f"更新 {stats['updated']}（{stats['owners']} 个用户空间）。")
    finally:
        await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
