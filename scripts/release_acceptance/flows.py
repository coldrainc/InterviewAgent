from __future__ import annotations

import base64
import time
import uuid
from typing import Any

from .api_client import ApiClient, expect


PASSWORD = "Release-check-2026!"


def _register(client: ApiClient, label: str) -> tuple[ApiClient, dict[str, Any]]:
    unique = uuid.uuid4().hex[:12]
    email = f"release-{label}-{unique}@example.invalid"
    data = expect(
        client.request(
            "POST",
            "/auth/register",
            json_body={"email": email, "password": PASSWORD, "display_name": f"验收用户 {label}"},
        ),
        200,
        f"注册用户 {label}",
    )
    return ApiClient(client.base_url, data["access_token"]), {
        "email": email,
        "user_id": data["user_id"],
        "refresh_token": data["refresh_token"],
    }


def run_full_acceptance(base_url: str) -> dict[str, Any]:
    public = ApiClient(base_url)
    health = expect(public.request("GET", "/health"), 200, "服务健康检查")
    if health.get("auth_required") is not True:
        raise AssertionError("服务未强制鉴权，不能作为上线验收环境")
    expect(public.request("GET", "/settings"), 401, "未登录访问受保护资源")
    expect(
        public.request("POST", "/auth/dev-login", json_body={"user_id": "forbidden"}),
        403,
        "开发登录已关闭",
    )

    user_a, account_a = _register(public, "a")
    user_b, account_b = _register(public, "b")
    me = expect(user_a.request("GET", "/me"), 200, "读取当前账号")
    assert me["user_id"] == account_a["user_id"]
    refreshed = expect(
        public.request(
            "POST",
            "/auth/refresh",
            json_body={"refresh_token": account_a["refresh_token"]},
        ),
        200,
        "刷新访问令牌并轮换 refresh token",
    )
    user_a = ApiClient(base_url, refreshed["access_token"])
    account_a["refresh_token"] = refreshed["refresh_token"]
    expect(
        public.request(
            "POST",
            "/auth/login",
            json_body={"email": account_a["email"], "password": PASSWORD},
        ),
        200,
        "密码重新登录",
    )

    expect(
        user_a.request("PUT", "/settings", json_body={"default_interview_mode": "candidate"}),
        200,
        "更新用户设置",
    )
    settings = expect(user_a.request("GET", "/settings"), 200, "读取用户设置")
    assert settings["default_interview_mode"] == "candidate"

    resume_text = "# 上线验收简历\n\n负责 Agent Harness、RAG 评测、灰度、监控与回滚。"
    encoded = base64.b64encode(resume_text.encode()).decode()
    expect(
        user_a.request("POST", "/resume/parse", json_body={"filename": "acceptance.md", "content_base64": encoded}),
        200,
        "解析简历",
    )
    resume = expect(
        user_a.request("POST", "/resumes", json_body={"filename": "acceptance.md", "content_base64": encoded}),
        200,
        "保存简历",
    )
    resume_id = resume["id"]
    assert expect(user_a.request("GET", "/resumes"), 200, "列出自己的简历")
    expect(user_a.request("GET", f"/resumes/{resume_id}"), 200, "读取自己的简历")
    expect(user_b.request("GET", f"/resumes/{resume_id}"), 404, "隔离其他用户简历")

    kit = expect(
        user_a.request(
            "POST",
            "/interviewer-workspace/kits",
            json_body={"target_role": "Agent 工程师", "seniority": "senior", "duration_minutes": 45},
        ),
        200,
        "创建面试官题纲",
    )
    kit_id = kit["id"]
    expect(user_b.request("GET", f"/interviewer-workspace/kits/{kit_id}"), 404, "隔离其他用户题纲")
    updated_kit = expect(
        user_a.request(
            "PUT",
            f"/interviewer-workspace/kits/{kit_id}/questions",
            json_body={
                "expected_version": kit["version"],
                "questions": [{"text": "如何设计可恢复的 Agent Harness？", "dimension": kit["dimensions"][0]}],
            },
        ),
        200,
        "版本化更新面试题纲",
    )
    assert updated_kit["version"] == kit["version"] + 1

    forged = user_b.request(
        "POST",
        "/sessions",
        json_body={"offline": True, "resume_id": resume_id, "interviewer_kit_id": kit_id},
    )
    expect(forged, 404, "阻断跨用户简历与题纲绑定")
    session = expect(
        user_a.request(
            "POST",
            "/sessions",
            json_body={
                "offline": True,
                "resume_id": resume_id,
                "interviewer_kit_id": kit_id,
                "target_role": "Agent 工程师",
            },
        ),
        200,
        "创建离线面试会话",
    )
    session_id = session["session_id"]
    expect(user_b.request("GET", f"/sessions/{session_id}"), 404, "隔离其他用户面试会话")
    expect(
        user_a.request(
            "POST",
            f"/sessions/{session_id}/messages",
            json_body={"message": "我负责状态机、工具权限、幂等恢复和链路观测，灰度后错误率下降 30%。"},
        ),
        200,
        "面试消息链路",
    )
    stream = expect(
        user_a.request(
            "POST",
            f"/sessions/{session_id}/stream",
            json_body={"message": "补充说明：通过回放测试和回滚开关控制上线风险。"},
            timeout=60,
        ),
        200,
        "面试 SSE 流式链路",
    )
    assert "event: message.done" in stream
    transcript = expect(user_a.request("GET", f"/sessions/{session_id}/transcript"), 200, "读取面试转录")
    assert transcript["transcript"]
    expect(
        user_a.request("POST", f"/sessions/{session_id}/rewind", json_body={"turn_index": 1}),
        200,
        "撤回到指定轮次",
    )
    expect(
        user_a.request(
            "POST",
            f"/interviewer-workspace/kits/{kit_id}/evidence",
            json_body={
                "client_key": "acceptance-evidence",
                "session_id": session_id,
                "dimension": kit["dimensions"][0],
                "signal": "positive",
                "note": "能说明状态、权限和恢复机制。",
            },
        ),
        200,
        "记录面试官评价证据",
    )

    expect(user_a.request("POST", "/practice/questions/seed"), 200, "初始化个人题库")
    questions = expect(
        user_a.request("GET", "/practice/questions?category=civil_service&limit=20"),
        200,
        "查询题库",
    )
    question = questions["items"][0]
    answer = question.get("answer") or "A"
    attempt = expect(
        user_a.request(
            "POST",
            "/practice/attempt",
            json_body={"question_id": question["id"], "answer": answer, "elapsed_seconds": 9},
        ),
        200,
        "提交并判定练习答案",
    )
    assert 0 <= attempt["score"] <= 100
    expect(user_a.request("GET", "/review-site/wrong-book"), 200, "读取错题本")
    drill = expect(
        user_a.request("POST", "/training/drills", json_body={"count": 3}),
        200,
        "创建专项训练",
    )
    drill_id = drill["id"]
    expect(user_a.request("POST", f"/training/drills/{drill_id}/complete"), 200, "完成专项训练")
    expect(user_b.request("GET", f"/training/drills/{drill_id}"), 404, "隔离其他用户训练")
    expect(user_a.request("POST", "/training/spaced-review/sync"), 200, "同步间隔复习")
    expect(user_a.request("GET", "/training/spaced-review/due"), 200, "读取待复习内容")

    plan_result = expect(
        user_a.request(
            "POST",
            "/review-site/planner/generate",
            json_body={
                "target_role": "Agent 工程师",
                "seniority": "senior",
                "total_days": 7,
                "hours_per_day": 2,
                "template": "rule-based",
                "resume_id": resume_id,
            },
        ),
        200,
        "生成复习计划",
    )
    plan_id = plan_result["plan_id"]
    plan = expect(user_a.request("GET", f"/review-site/plans/{plan_id}"), 200, "读取复习计划")
    expect(user_b.request("GET", f"/review-site/plans/{plan_id}"), 404, "隔离其他用户复习计划")
    expect(
        user_a.request("PATCH", f"/review-site/plans/{plan_id}", json_body={"status": "active"}),
        200,
        "激活复习计划",
    )
    today = expect(user_a.request("GET", f"/review-site/plans/{plan_id}/today"), 200, "读取今日复习")
    assert today["active"] is True and today["tasks"]
    task_id = today["tasks"][0]["id"]
    expect(
        user_a.request(
            "PATCH",
            f"/review-site/progress/task/{task_id}",
            json_body={"done": True, "elapsed_minutes": 25, "mastery_score": 4, "note": "验收完成"},
        ),
        200,
        "完成计划任务",
    )
    expect(
        user_a.request(
            "POST",
            f"/review-site/plans/{plan_id}/checkin",
            json_body={"elapsed_minutes": 25, "note": "上线验收打卡"},
        ),
        200,
        "复习计划打卡",
    )
    expect(user_a.request("GET", "/review-site/checkins"), 200, "读取打卡记录")
    expect(user_a.request("GET", "/study/dashboard"), 200, "读取学习仪表盘")
    expect(user_a.request("GET", "/study/achievements"), 200, "读取学习成就")

    goal = expect(
        user_a.request(
            "PUT",
            "/learning/goals/active",
            json_body={"title": "完成 Agent 面试准备", "target_role": "Agent 工程师", "daily_minutes": 60},
        ),
        200,
        "创建学习目标",
    )
    assert goal["title"]
    expect(user_a.request("GET", "/learning/ability-snapshot?refresh=true"), 200, "计算能力快照")
    expect(user_a.request("GET", "/learning/today"), 200, "读取 Harness 今日任务")
    expect(user_a.request("GET", "/learning/sync"), 200, "读取多端同步游标")

    job = expect(
        user_a.request(
            "POST",
            "/workflows/run",
            json_body={"workflow_type": "workflow", "title": "上线验收工作流", "input": {"scenario": "interview_readiness"}},
        ),
        200,
        "启动 Agent 工作流",
    )
    job_id = job["id"]
    terminal_job = _wait_for_job(user_a, job_id)
    assert terminal_job["status"] == "succeeded", terminal_job
    print("PASS  Agent 工作流完成")
    expect(user_b.request("GET", f"/jobs/{job_id}"), 404, "隔离其他用户 Agent 工作流")
    traces = expect(user_a.request("GET", "/ops/traces"), 200, "读取 Agent Trace")
    assert traces
    expect(user_a.request("GET", f"/ops/traces/{traces[0]['id']}"), 200, "读取 Agent Trace 详情")
    expect(user_a.request("GET", "/ops/metrics"), 200, "读取运行指标")

    exported = expect(user_a.request("GET", "/privacy/export"), 200, "导出个人数据")
    export_text = str(exported).lower()
    assert "password_hash" not in export_text and "access_token" not in export_text
    expect(
        user_a.request(
            "POST",
            "/privacy/deletion",
            json_body={"confirmation": "DELETE", "reason": "隔离环境验收后取消"},
        ),
        200,
        "申请删除账号",
    )
    expect(user_a.request("DELETE", "/privacy/deletion"), 200, "取消删除申请")

    return {
        "email": account_a["email"],
        "user_id": account_a["user_id"],
        "resume_id": resume_id,
        "session_id": session_id,
        "kit_id": kit_id,
        "drill_id": drill_id,
        "plan_id": plan_id,
        "job_id": job_id,
        "other_user_id": account_b["user_id"],
    }


def verify_persistence(base_url: str, state: dict[str, Any]) -> None:
    public = ApiClient(base_url)
    login = expect(
        public.request(
            "POST", "/auth/login", json_body={"email": state["email"], "password": PASSWORD}
        ),
        200,
        "重启后重新登录",
    )
    client = ApiClient(base_url, login["access_token"])
    for path, label in [
        (f"/resumes/{state['resume_id']}", "简历持久化"),
        (f"/sessions/{state['session_id']}", "面试会话持久化"),
        (f"/interviewer-workspace/kits/{state['kit_id']}", "面试题纲持久化"),
        (f"/training/drills/{state['drill_id']}", "训练记录持久化"),
        (f"/review-site/plans/{state['plan_id']}", "复习计划持久化"),
        (f"/jobs/{state['job_id']}", "Agent 工作流持久化"),
    ]:
        expect(client.request("GET", path), 200, label)


def logout_and_verify_refresh_revoked(base_url: str, state: dict[str, Any]) -> None:
    public = ApiClient(base_url)
    login = expect(
        public.request(
            "POST", "/auth/login", json_body={"email": state["email"], "password": PASSWORD}
        ),
        200,
        "登出验收前登录",
    )
    client = ApiClient(base_url, login["access_token"])
    expect(
        client.request("POST", "/auth/logout", json_body={"refresh_token": login["refresh_token"]}),
        200,
        "登出并撤销 refresh token",
    )
    expect(
        public.request("POST", "/auth/refresh", json_body={"refresh_token": login["refresh_token"]}),
        401,
        "已撤销 refresh token 不可重放",
    )


def _wait_for_job(client: ApiClient, job_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        job = expect(client.request("GET", f"/jobs/{job_id}"), 200, "轮询 Agent 工作流")
        if job["status"] in {"succeeded", "failed", "canceled"}:
            return job
        time.sleep(0.2)
    raise AssertionError("Agent 工作流在 30 秒内未结束")
