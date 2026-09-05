"""LLM 个性化复习计划生成。

基于用户画像（岗位/职级/公司/天数/日时长/重点方向）、简历摘要、
历史面试报告薄弱点与错题本，调用 LLM 生成阶段-天-任务三级计划，
任务携带 reason 与可跳转 link（模拟面试 / 刷题 / 知识库资料）。

LLM 不可用、余额不足或返回非法结构时返回 None，由 API 层降级为规则模板。
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.infrastructure.db.models import ResumeModel
from interview_agent.repositories.interview_report_repository import InterviewReportRepository
from interview_agent.repositories.practice_question_repository import PracticeQuestionRepository
from interview_agent.repositories.review_site_repository import ReviewSiteRepository

logger = logging.getLogger(__name__)

DEFAULT_PHASES = [
    ("p1", "基础储备", 0.22, "简历与自我介绍熟背、核心知识与题库第一轮通读。"),
    ("p2", "深挖对齐", 0.28, "项目深挖 STAR 打磨、岗位专项知识与答题框架。"),
    ("p3", "模拟冲刺", 0.28, "多场全真模拟、错题本清零、弱点清单二刷。"),
    ("p4", "面试前速记", 0.22, "速记单回顾、定制模拟、状态管理，最后一天不学新内容。"),
]

VALID_TASK_KINDS = {"study", "practice", "simulation", "material", "review"}


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    """从 LLM 输出中提取最外层 JSON 对象，容忍 ```json 代码块与前后说明文字。"""
    if not raw:
        return None
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


class PlanGeneratorService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        user_id: str,
        llm: Any = None,
        model_id: str = "",
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.llm = llm
        self.model_id = model_id

    async def generate(
        self,
        *,
        title: str | None,
        target_role: str,
        seniority: str,
        target_company: str | None,
        total_days: int,
        hours_per_day: float,
        focus_areas: list[str] | None,
        resume_id: str | None = None,
        use_history: bool = True,
    ) -> dict[str, Any] | None:
        """生成并持久化计划；LLM 失败时返回 None（调用方降级规则模板）。"""
        if self.llm is None:
            return None
        context = await self._build_context(resume_id=resume_id, use_history=use_history)
        prompt = self._build_prompt(
            target_role=target_role,
            seniority=seniority,
            target_company=target_company,
            total_days=total_days,
            hours_per_day=hours_per_day,
            focus_areas=focus_areas or [],
            context=context,
        )
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            response = await self.llm.ainvoke([
                SystemMessage(content=(
                    "你是资深面试辅导教练，擅长根据候选人画像、历史面试表现和错题记录，"
                    "制定分阶段、可执行、每日可打卡的复习计划。"
                    "只输出一个 JSON 对象，不要输出任何解释或 markdown。"
                )),
                HumanMessage(content=prompt),
            ])
            raw = response.content if hasattr(response, "content") else str(response)
        except Exception:
            logger.exception("LLM plan generation call failed")
            return None

        data = _extract_json_object(raw if isinstance(raw, str) else str(raw))
        if data is None:
            logger.warning("LLM plan generation returned non-JSON content")
            return None
        payload = self._normalize(
            data,
            title=title,
            target_role=target_role,
            seniority=seniority,
            target_company=target_company,
            total_days=total_days,
            hours_per_day=hours_per_day,
            focus_areas=focus_areas or [],
        )
        if payload is None:
            logger.warning("LLM plan generation payload invalid")
            return None
        try:
            repo = ReviewSiteRepository(self.session, tenant_id=self.tenant_id, user_id=self.user_id)
            plan = await repo.create_plan(
                plan_data=payload["plan"],
                phases=payload["phases"],
                days=payload["days"],
                tasks_per_day=payload["tasks_per_day"],
                intro_scripts=[],
                star_cards=[],
                a4_memory=[],
            )
        except Exception:
            logger.exception("persist LLM plan failed")
            return None
        return {
            "plan": plan,
            "breakdown": payload["breakdown"],
            "generated_by": "llm",
            "model_id": self.model_id,
            "prompt_text": prompt,
            "response_text": raw if isinstance(raw, str) else str(raw),
        }

    async def _build_context(self, *, resume_id: str | None, use_history: bool) -> dict[str, Any]:
        context: dict[str, Any] = {"resume_summary": "", "reports": [], "wrong_questions": []}
        if resume_id:
            try:
                resume_uuid = uuid.UUID(str(resume_id))
                result = await self.session.execute(
                    select(ResumeModel).where(
                        ResumeModel.tenant_id == self.tenant_id,
                        ResumeModel.user_id == self.user_id,
                        ResumeModel.id == resume_uuid,
                    )
                )
                resume = result.scalar_one_or_none()
                if resume:
                    context["resume_summary"] = (resume.summary or "")[:1500]
            except (ValueError, TypeError):
                logger.warning("invalid resume_id for planner: %s", resume_id)
            except Exception:
                logger.exception("load resume for planner failed")
        if not use_history:
            return context
        try:
            reports = await InterviewReportRepository(
                self.session, tenant_id=self.tenant_id, user_id=self.user_id
            ).list_reports(limit=5)
            context["reports"] = [
                {
                    "target_role": r.get("target_role"),
                    "total_score": r.get("total_score"),
                    "weakness_tags": r.get("weakness_tags") or [],
                    "suggestions": (r.get("suggestions") or [])[:3],
                }
                for r in reports
            ]
        except Exception:
            logger.exception("load reports for planner failed")
        try:
            entries = await PracticeQuestionRepository(
                self.session, tenant_id=self.tenant_id, user_id=self.user_id
            ).list_wrong_book(mark_type="wrong", limit=10)
            context["wrong_questions"] = [
                {
                    "category": entry.get("practice_category") or entry.get("question", {}).get("practice_category"),
                    "prompt": (entry.get("prompt") or entry.get("question", {}).get("prompt") or "")[:120],
                }
                for entry in entries
            ]
        except Exception:
            logger.exception("load wrong book for planner failed")
        return context

    def _build_prompt(
        self,
        *,
        target_role: str,
        seniority: str,
        target_company: str | None,
        total_days: int,
        hours_per_day: float,
        focus_areas: list[str],
        context: dict[str, Any],
    ) -> str:
        return f"""请为以下候选人生成 {total_days} 天面试复习计划（每日可投入 {hours_per_day} 小时）。

候选人画像：
- 目标岗位：{target_role or '未指定'}
- 职级：{seniority or '未指定'}
- 目标公司：{target_company or '未指定'}
- 重点方向：{', '.join(focus_areas) if focus_areas else '无'}

简历摘要：
{context.get('resume_summary') or '（未提供简历）'}

历史面试报告（含薄弱点标签）：
{json.dumps(context.get('reports') or [], ensure_ascii=False) or '（暂无历史面试）'}

错题本（待攻克题目）：
{json.dumps(context.get('wrong_questions') or [], ensure_ascii=False) or '（暂无错题记录）'}

输出 JSON 结构：
{{
  "phases": [{{"key": "p1", "title": "阶段名", "goal": "阶段目标", "ratio": 0.25}}],
  "days": [
    {{
      "day_index": 1,
      "phase": "p1",
      "title": "当天主题",
      "acceptance": "当天验收标准（可衡量）",
      "tasks": [
        {{
          "title": "任务标题",
          "kind": "study | practice | simulation | material",
          "reason": "为什么安排这个任务（结合薄弱点/错题/简历）",
          "tags": ["标签"],
          "critical": false,
          "mode": "interviewer 或 candidate（仅 simulation）",
          "focus": "模拟面试考察重点（仅 simulation）",
          "category": "刷题分类，如 internet/civil-service（仅 practice）"
        }}
      ]
    }}
  ]
}}

要求：
1. phases 的 ratio 之和为 1，阶段数 3-5 个；days 必须恰好 {total_days} 天，day_index 从 1 连续编号。
2. 每天 2-4 个任务，任务总量与每日 {hours_per_day} 小时匹配。
3. 每个任务必须给 reason；模拟面试任务 kind=simulation 并给 mode 与 focus；
   刷题任务 kind=practice 并给 category；资料学习 kind=material。
4. 优先针对薄弱点标签与错题本分类安排练习，后期阶段模拟面试密度要更高。
5. 最后一天安排速记与状态调整，不安排新内容。
只输出 JSON 对象。"""

    def _normalize(
        self,
        data: dict[str, Any],
        *,
        title: str | None,
        target_role: str,
        seniority: str,
        target_company: str | None,
        total_days: int,
        hours_per_day: float,
        focus_areas: list[str],
    ) -> dict[str, Any] | None:
        raw_phases = data.get("phases")
        raw_days = data.get("days")
        if not isinstance(raw_days, list) or not raw_days:
            return None

        phases = self._normalize_phases(raw_phases if isinstance(raw_phases, list) else [])
        phase_keys = [p["key"] for p in phases]

        days_in = sorted(
            (d for d in raw_days if isinstance(d, dict)),
            key=lambda d: d.get("day_index") if isinstance(d.get("day_index"), int) else 0,
        )
        days_data: list[dict[str, Any]] = []
        tasks_per_day: dict[str, list[dict[str, Any]]] = {}
        breakdown: list[dict[str, Any]] = []

        phase_day_counts = {key: 0 for key in phase_keys}
        for day_num in range(1, total_days + 1):
            day_src = next((d for d in days_in if d.get("day_index") == day_num), None)
            if day_src is None:
                day_src = days_in[day_num - 1] if day_num - 1 < len(days_in) else None
            phase_key = self._resolve_phase_key(
                (day_src or {}).get("phase") or (day_src or {}).get("phase_key"),
                phase_keys,
                day_num,
                total_days,
            )
            phase_day_counts[phase_key] = phase_day_counts.get(phase_key, 0) + 1
            day_key = f"day-{day_num}"
            day_title = str((day_src or {}).get("title") or "").strip() or f"第 {day_num} 天 · {target_role or '面试'}专项"
            acceptance = str((day_src or {}).get("acceptance") or "").strip()
            days_data.append({
                "id": day_key,
                "day": f"Day {day_num}",
                "phase": phase_key,
                "title": day_title,
                "acceptance": acceptance,
            })
            tasks = self._normalize_tasks((day_src or {}).get("tasks"), day_num=day_num)
            if not tasks:
                tasks = [self._fallback_task(phase_key, day_num)]
            tasks_per_day[day_key] = tasks

        cursor = 0
        for idx, phase in enumerate(phases):
            count = phase_day_counts.get(phase["key"], 0)
            if idx == len(phases) - 1:
                count = total_days - cursor
            start_day = cursor + 1
            end_day = cursor + count
            range_label = f"Day{start_day}-{end_day}" if start_day != end_day else f"Day{start_day}"
            breakdown.append({
                "phase_key": phase["key"],
                "title": phase["title"],
                "range_label": range_label,
                "days": count,
                "estimated_hours": round(count * hours_per_day, 1),
                "goal": phase["goal"],
            })
            cursor += count

        plan_title = title or f"{target_role or '面试'} {total_days} 天复习计划"
        if not title and seniority:
            plan_title += f" ({seniority})"
        plan_data = {
            "plan_key": f"llm-{total_days}d-{int(time.time())}",
            "title": plan_title,
            "subtitle": f"总时长 {total_days} 天 × 日均 {hours_per_day}h · AI 个性化生成",
            "description": self._build_description(target_role, seniority, target_company, total_days, hours_per_day, focus_areas),
            "status": "draft",
            "source_root": "",
            "source_documents": [],
            "commercial_positioning": [],
            "metadata": {
                "generated": True,
                "generated_by": "llm",
                "model_id": self.model_id,
                "target_role": target_role,
                "seniority": seniority,
                "target_company": target_company or "",
                "total_days": total_days,
                "hours_per_day": hours_per_day,
                "focus_areas": focus_areas,
            },
        }
        phases_data = [
            {
                "id": phase["key"],
                "title": phase["title"],
                "range": "",
                "goal": phase["goal"],
            }
            for phase in phases
        ]
        return {
            "plan": plan_data,
            "phases": phases_data,
            "days": days_data,
            "tasks_per_day": tasks_per_day,
            "breakdown": breakdown,
        }

    def _normalize_phases(self, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        phases: list[dict[str, Any]] = []
        for idx, item in enumerate(raw[:5]):
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or item.get("id") or f"p{idx + 1}")[:32]
            title = str(item.get("title") or item.get("name") or f"阶段 {idx + 1}")[:64]
            goal = str(item.get("goal") or "")[:500]
            try:
                ratio = float(item.get("ratio") or 0)
            except (TypeError, ValueError):
                ratio = 0.0
            phases.append({"key": key, "title": title, "goal": goal, "ratio": ratio})
        if len(phases) < 2:
            return [
                {"key": key, "title": t, "goal": g, "ratio": r}
                for key, t, r, g in DEFAULT_PHASES
            ]
        total_ratio = sum(p["ratio"] for p in phases)
        if total_ratio <= 0:
            for p in phases:
                p["ratio"] = 1.0 / len(phases)
        else:
            for p in phases:
                p["ratio"] = max(0.05, p["ratio"] / total_ratio)
        return phases

    def _resolve_phase_key(
        self, raw_key: Any, phase_keys: list[str], day_num: int, total_days: int
    ) -> str:
        if raw_key and str(raw_key) in phase_keys:
            return str(raw_key)
        progress = day_num / max(total_days, 1)
        idx = min(int(progress * len(phase_keys)), len(phase_keys) - 1)
        return phase_keys[idx]

    def _normalize_tasks(self, raw_tasks: Any, *, day_num: int) -> list[dict[str, Any]]:
        if not isinstance(raw_tasks, list):
            return []
        tasks: list[dict[str, Any]] = []
        for item in raw_tasks[:6]:
            if not isinstance(item, dict):
                continue
            task_title = str(item.get("title") or "").strip()
            if not task_title:
                continue
            kind = str(item.get("kind") or item.get("type") or "study").strip().lower()
            if kind not in VALID_TASK_KINDS:
                kind = "study"
            task: dict[str, Any] = {
                "title": task_title[:200],
                "tags": [str(t)[:32] for t in (item.get("tags") or [])][:6],
                "critical": bool(item.get("critical", False)),
                "reason": str(item.get("reason") or "").strip()[:300],
                "source": "llm",
                "docs": [],
            }
            if kind == "simulation":
                mode = str(item.get("mode") or "interviewer").strip().lower()
                if mode not in ("interviewer", "candidate"):
                    mode = "interviewer"
                task["simulation"] = True
                task["link_type"] = "interview"
                task["link_payload"] = {"mode": mode, "focus": str(item.get("focus") or "")[:200]}
                task["tags"] = task["tags"] or ["模拟面试"]
            elif kind == "practice":
                category = str(item.get("category") or "internet").strip()[:32]
                task["link_type"] = "practice"
                task["link_payload"] = {"category": category}
                task["tags"] = task["tags"] or ["刷题"]
            elif kind == "material":
                ref = str(item.get("ref") or item.get("key") or "").strip()[:200]
                task["link_type"] = "knowledge"
                task["link_payload"] = {"key": ref}
                task["tags"] = task["tags"] or ["资料"]
            else:
                task["link_type"] = "none"
                task["link_payload"] = {}
            tasks.append(task)
        return tasks

    def _fallback_task(self, phase_key: str, day_num: int) -> dict[str, Any]:
        if phase_key == "p3":
            return {
                "title": "完成 1 场全真模拟面试并复盘",
                "tags": ["模拟面试"],
                "critical": True,
                "reason": "冲刺阶段保持模拟密度，暴露临场问题",
                "source": "llm",
                "simulation": True,
                "link_type": "interview",
                "link_payload": {"mode": "interviewer", "focus": "综合能力考察"},
                "docs": [],
            }
        return {
            "title": "复习今日内容并整理笔记要点",
            "tags": ["复习"],
            "critical": False,
            "reason": "巩固当天学习内容，形成可回顾笔记",
            "source": "llm",
            "link_type": "none",
            "link_payload": {},
            "docs": [],
        }

    def _build_description(
        self,
        target_role: str,
        seniority: str,
        target_company: str | None,
        total_days: int,
        hours_per_day: float,
        focus_areas: list[str],
    ) -> str:
        parts = [f"AI 根据{target_role or '目标岗位'}"]
        if seniority:
            parts.append(f"（{seniority}）")
        parts.append(f"画像生成的 {total_days} 天复习计划，日均 {hours_per_day} 小时")
        if target_company:
            parts.append(f"，目标公司 {target_company}")
        if focus_areas:
            parts.append(f"，重点方向：{'、'.join(focus_areas)}")
        parts.append("。任务结合历史面试薄弱点与错题记录自动编排。")
        return "".join(parts)
