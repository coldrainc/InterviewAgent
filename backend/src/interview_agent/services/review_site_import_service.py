from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.domain.review_site import DEFAULT_REVIEW_SITE, INTERVIEW_CONTENT_ROOT
from interview_agent.repositories.practice_question_repository import (
    PracticeQuestionRepository,
    question_content_hash,
)
from interview_agent.repositories.review_site_repository import ReviewSiteRepository

logger = logging.getLogger(__name__)


class ReviewSiteImportService:
    def __init__(
        self,
        session: AsyncSession,
        tenant_id: str = "default",
        user_id: str = "anonymous",
        content_root: str | None = None,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.content_root = Path(content_root or INTERVIEW_CONTENT_ROOT)
        self.plan_repo = ReviewSiteRepository(session, tenant_id, user_id)
        self.question_repo = PracticeQuestionRepository(session, tenant_id, user_id)

    async def run_import(
        self,
        *,
        plan_only: bool = False,
        questions_only: bool = False,
    ) -> dict[str, int]:
        plan_count = 0
        question_count = 0
        wrong_book_count = 0

        if not questions_only:
            plan_count = await self.import_default_plan()
        if not plan_only:
            result = await self.import_interview_question_folder()
            question_count = result.get("created", 0) + result.get("updated", 0)
        wrong_book_count = len(await self.question_repo.list_wrong_book())
        return {
            "plan_count": plan_count,
            "question_count": question_count,
            "wrong_book_count": wrong_book_count,
        }

    async def import_default_plan(self) -> int:
        plan_info = DEFAULT_REVIEW_SITE.get("plan") or {}
        plan_key = str(plan_info.get("id") or "")
        existing = await self.plan_repo.get_plan_by_key(plan_key)
        if existing:
            return 0
        await self.plan_repo.seed_plan_from_default(DEFAULT_REVIEW_SITE)
        return 1

    async def import_interview_question_folder(self) -> dict[str, int]:
        root = self.content_root / "面试题"
        items: list[dict[str, Any]] = []

        if (root / "readme.md").exists():
            try:
                text = (root / "readme.md").read_text(encoding="utf-8")
                items.extend(_parse_bullet_readme(text, source="readme.md"))
            except Exception as exc:
                logger.warning(f"parse readme.md failed: {exc}")

        for js_file in [root / "快手.js", root / "蚂蚁证券_AI_Native.js"]:
            if js_file.exists():
                try:
                    text = js_file.read_text(encoding="utf-8")
                    items.extend(_parse_js_question_file(text, source=js_file.name))
                except Exception as exc:
                    logger.warning(f"parse {js_file.name} failed: {exc}")

        interview_dir = root / "interview"
        md_targets = [
            interview_dir / "interview_qna.md",
            interview_dir / "docs" / "interview_qna" / "面试问答.md",
            interview_dir / "docs" / "interview_qna" / "面试问答-详细话术.md",
        ]
        for md_file in md_targets:
            if md_file.exists():
                try:
                    text = md_file.read_text(encoding="utf-8")
                    items.extend(_parse_qna_markdown(text, source=md_file.name))
                except Exception as exc:
                    logger.warning(f"parse {md_file.name} failed: {exc}")

        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for item in items:
            prompt = str(item.get("prompt") or "").strip()
            if not prompt:
                continue
            answer = str(item.get("answer") or "")
            h = question_content_hash(prompt, answer)
            if h in seen:
                continue
            seen.add(h)
            item["content_hash"] = h
            deduped.append(item)

        if not deduped:
            return {"created": 0, "updated": 0, "total": 0}
        return await self.question_repo.bulk_upsert(deduped)


def _parse_bullet_readme(text: str, *, source: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    items: list[dict[str, Any]] = []
    current_prompt: str | None = None
    current_answer_lines: list[str] = []
    code_block: bool = False

    def flush() -> None:
        if not current_prompt:
            return
        answer = "\n".join(current_answer_lines).strip()
        prompt_clean = current_prompt.strip()
        if not prompt_clean:
            return
        prompt_clean = re.sub(r"^[-*+]\s*", "", prompt_clean).strip()
        if not prompt_clean:
            return
        items.append(_build_question(
            prompt=prompt_clean,
            answer=answer or None,
            source=source,
            category="internet",
            subject="frontend",
            qtype="js_basic" if _looks_like_code(prompt_clean) or code_block else "interview_qna",
        ))

    for line in lines:
        stripped = line.rstrip()
        if stripped.strip().startswith("```"):
            code_block = not code_block
            if current_prompt:
                current_answer_lines.append(stripped)
            continue
        if code_block and current_prompt:
            current_answer_lines.append(stripped)
            continue
        if re.match(r"^\s*[-*+]\s+", stripped):
            if current_prompt:
                flush()
            current_prompt = stripped
            current_answer_lines = []
        elif stripped and current_prompt is not None:
            indent = len(stripped) - len(stripped.lstrip())
            if indent > 0 or _looks_like_continuation(stripped):
                current_answer_lines.append(stripped.strip())
            else:
                flush()
                current_prompt = stripped
                current_answer_lines = []

    if current_prompt:
        flush()
    return items


def _parse_js_question_file(text: str, *, source: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    comment_blocks = re.findall(r"/\*([\s\S]*?)\*/", text)
    for block in comment_blocks:
        cleaned = re.sub(r"^\s*\*+", "", block, flags=re.MULTILINE).strip()
        if cleaned and len(cleaned) > 4:
            items.append(_build_question(
                prompt=cleaned,
                answer=None,
                source=source,
                category="leetcode" if _looks_like_algorithm(cleaned) else "internet",
                subject="algorithm" if _looks_like_algorithm(cleaned) else "frontend",
                qtype="algorithm" if _looks_like_algorithm(cleaned) else "interview_qna",
            ))
    code_snippets = _extract_code_snippets(text)
    for prompt, answer in code_snippets:
        items.append(_build_question(
            prompt=prompt,
            answer=answer,
            source=source,
            category="leetcode",
            subject="algorithm",
            qtype="algorithm",
        ))
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for line in lines:
        if line.startswith("//") or line.startswith("/*") or line.startswith("*"):
            continue
        if re.match(r"^[a-zA-Z\u4e00-\u9fa5].{1,80}$", line) and not line.endswith(";") and not line.endswith("{") and not line.endswith("}"):
            if not any(item.get("prompt") == line for item in items):
                items.append(_build_question(
                    prompt=line,
                    answer=None,
                    source=source,
                    category="leetcode" if _looks_like_algorithm(line) else "internet",
                    subject="algorithm" if _looks_like_algorithm(line) else "frontend",
                    qtype="algorithm" if _looks_like_algorithm(line) else "interview_qna",
                ))
    return items


def _extract_code_snippets(text: str) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    pattern = re.compile(
        r"//\s*(.+?)\s*\n([\s\S]*?)(?=\n//|\Z)",
        re.MULTILINE,
    )
    for match in pattern.finditer(text):
        title = match.group(1).strip()
        code = match.group(2).strip()
        if len(title) <= 120 and len(code) > 10:
            results.append((title, code))
    return results


def _parse_qna_markdown(text: str, *, source: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    blocks = re.split(r"\n---\n|\n## |\n### ", text)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        q, a = _split_qa_block(block)
        if q and (q.endswith("？") or q.endswith("?") or "：" in q[:20] or len(q) <= 120):
            q_clean = re.sub(r"^\d+[\.\、]\s*", "", q).strip()
            q_clean = re.sub(r"^Q[:：]\s*", "", q_clean).strip()
            q_clean = re.sub(r"^\*\*Q[:：]?\*\*\s*", "", q_clean).strip()
            q_clean = re.sub(r"^##\s*", "", q_clean).strip()
            q_clean = re.sub(r"^###\s*", "", q_clean).strip()
            if q_clean and len(q_clean) >= 4:
                items.append(_build_question(
                    prompt=q_clean,
                    answer=a or None,
                    source=source,
                    category="internet",
                    subject=_infer_subject(q_clean + " " + (a or "")),
                    qtype="interview_qna",
                ))
    return items


def _split_qa_block(block: str) -> tuple[str, str]:
    first_line_end = block.find("\n")
    if first_line_end < 0:
        return block, ""
    q = block[:first_line_end].strip()
    a = block[first_line_end + 1:].strip()
    a = re.sub(r"^\*\*A[:：]?\*\*\s*", "", a).strip()
    a = re.sub(r"^A[:：]\s*", "", a).strip()
    a = re.sub(r"^\*\*参考要点\*\*[:：]?\s*", "", a).strip()
    return q, a


def _build_question(
    *,
    prompt: str,
    answer: str | None,
    source: str,
    category: str,
    subject: str | None,
    qtype: str | None,
) -> dict[str, Any]:
    difficulty = "medium"
    tags: list[str] = []
    if subject:
        tags.append(subject)
    if qtype:
        tags.append(qtype)
    if source:
        tags.append(source.replace(".md", "").replace(".js", ""))
    return {
        "practice_category": category,
        "source": source,
        "source_url": None,
        "subject": subject,
        "question_type": qtype,
        "prompt": prompt.strip(),
        "choices_json": None,
        "answer": answer.strip() if answer else None,
        "answer_detail": None,
        "difficulty": difficulty,
        "tags_json": [t for t in tags if t][:10],
        "metadata_json": {"import_from": source},
    }


def _looks_like_continuation(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if re.match(r"^[\u4e00-\u9fa5a-zA-Z]", stripped):
        return True
    return False


def _looks_like_code(text: str) -> bool:
    markers = ["function ", "class ", "var ", "const ", "let ", "=>", "{", "}", "return "]
    return any(m in text for m in markers)


def _looks_like_algorithm(text: str) -> bool:
    keywords = ["之和", "两数", "三数", "链表", "二叉树", "树", "动态规划", "算法", "复杂度", "排序",
                "LRU", "深拷贝", "防抖", "节流", "Promise", "柯里", "链表", "手写",
                "leetcode", "LeetCode", "力扣", "sum", "tree", "dp", "dfs", "bfs"]
    lowered = text.lower()
    return any(k.lower() in lowered for k in keywords)


def _infer_subject(text: str) -> str | None:
    lowered = text.lower()
    mapping = [
        ("鸿蒙", "harmonyos"),
        ("arkts", "harmonyos"),
        ("arkui", "harmonyos"),
        ("kmp", "kmp"),
        ("跨端", "cross_platform"),
        ("跨平台", "cross_platform"),
        ("rn ", "react_native"),
        ("react native", "react_native"),
        ("lynx", "lynx"),
        ("hybrid", "hybrid"),
        ("微前端", "micro_frontend"),
        ("agent", "ai_agent"),
        ("workflow", "ai_agent"),
        ("harness", "ai_agent"),
        ("rag", "rag"),
        ("向量", "rag"),
        ("llm", "llm"),
        ("大模型", "llm"),
        ("react", "frontend"),
        ("vue", "frontend"),
        ("webpack", "frontend"),
        ("babel", "frontend"),
        ("http", "network"),
        ("tcp", "network"),
        ("udp", "network"),
        ("浏览器", "frontend"),
        ("js", "frontend"),
        ("javascript", "frontend"),
        ("typescript", "frontend"),
        ("electron", "fullstack"),
        ("全栈", "fullstack"),
        ("nest", "fullstack"),
    ]
    for k, v in mapping:
        if k.lower() in lowered:
            return v
    return "interview"
