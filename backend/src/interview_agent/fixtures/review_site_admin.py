from __future__ import annotations

from typing import Any


ADMIN_REVIEW_SITE_FIXTURE: dict[str, Any] = {
    "plan": {
        "id": "admin-review-site-fixture-v1",
        "plan_key": "admin-review-site-fixture-v1",
        "title": "管理员测试计划",
        "subtitle": "7 天通用面试准备流程",
        "description": "仅用于非生产环境验证计划、任务、打卡和复习素材交互。",
        "status": "draft",
        "source_root": "",
        "source_documents": [],
        "commercial_positioning": [],
        "metadata": {"fixture": True, "fixture_kind": "admin_test"},
    },
    "phases": [
        {"id": "foundation", "title": "基础夯实", "range": "Day 1-2", "goal": "完成岗位画像和基础知识检查。"},
        {"id": "deepening", "title": "专题深挖", "range": "Day 3-4", "goal": "形成可复述的技术方案和项目案例。"},
        {"id": "project", "title": "表达打磨", "range": "Day 5-6", "goal": "使用 STAR 结构完成项目表达。"},
        {"id": "simulation", "title": "模拟冲刺", "range": "Day 7", "goal": "完成一次全流程模拟并复盘。"},
    ],
    "days": [
        {
            "id": "fixture-day-1", "day": "Day 1", "phase": "foundation", "title": "岗位与能力盘点",
            "tasks": [
                {"id": "fixture-task-1-1", "title": "整理目标岗位的五项核心能力", "tags": ["岗位画像"], "critical": True},
                {"id": "fixture-task-1-2", "title": "完成基础知识自测并标记薄弱项", "tags": ["自测"]},
            ],
        },
        {
            "id": "fixture-day-2", "day": "Day 2", "phase": "foundation", "title": "基础知识复习",
            "tasks": [
                {"id": "fixture-task-2-1", "title": "复习语言运行时与异步模型", "tags": ["基础"]},
                {"id": "fixture-task-2-2", "title": "完成五道基础练习题", "tags": ["练习"]},
            ],
        },
        {
            "id": "fixture-day-3", "day": "Day 3", "phase": "deepening", "title": "系统设计专题",
            "tasks": [
                {"id": "fixture-task-3-1", "title": "设计一个可扩展的任务调度服务", "tags": ["系统设计"], "critical": True},
                {"id": "fixture-task-3-2", "title": "补充容量、监控和降级方案", "tags": ["可靠性"]},
            ],
        },
        {
            "id": "fixture-day-4", "day": "Day 4", "phase": "deepening", "title": "Agent 工程专题",
            "tasks": [
                {"id": "fixture-task-4-1", "title": "说明工具调用的校验、超时和重试策略", "tags": ["Agent"]},
                {"id": "fixture-task-4-2", "title": "设计一组可重复执行的 Agent 评测用例", "tags": ["评测"]},
            ],
        },
        {
            "id": "fixture-day-5", "day": "Day 5", "phase": "project", "title": "项目案例整理",
            "tasks": [
                {"id": "fixture-task-5-1", "title": "按 STAR 结构整理一个虚构项目案例", "tags": ["STAR"], "critical": True},
                {"id": "fixture-task-5-2", "title": "准备三个项目追问及回答要点", "tags": ["表达"]},
            ],
        },
        {
            "id": "fixture-day-6", "day": "Day 6", "phase": "project", "title": "表达与追问",
            "tasks": [
                {"id": "fixture-task-6-1", "title": "录制九十秒通用自我介绍", "tags": ["表达"]},
                {"id": "fixture-task-6-2", "title": "整理五个高质量反向提问", "tags": ["沟通"]},
            ],
        },
        {
            "id": "fixture-day-7", "day": "Day 7", "phase": "simulation", "title": "全流程模拟",
            "acceptance": "完成模拟、记录三个改进点并制定下一轮行动。",
            "tasks": [
                {"id": "fixture-task-7-1", "title": "完成四十五分钟通用技术模拟", "tags": ["模拟"], "critical": True, "simulation": True},
                {"id": "fixture-task-7-2", "title": "根据反馈完成复盘和下一步计划", "tags": ["复盘"]},
            ],
        },
    ],
    "intro_scripts": [
        {
            "id": "fixture-intro-60", "label": "通用版", "duration_seconds": 60, "scenario": "技术面试",
            "text": "你好，我是一名测试候选人。我的经历覆盖产品开发、系统设计和工程质量建设。接下来我会用一个虚构项目说明问题拆解、方案取舍和结果复盘。",
        }
    ],
    "star_cards": [
        {
            "id": "fixture-star-1", "title": "虚构任务平台改造", "tag": "系统设计",
            "background": "测试团队需要统一管理异步任务。", "challenge": "任务状态分散且失败原因难以定位。",
            "solution": "建立统一状态机、幂等执行、重试策略和可观测链路。", "result": "测试环境成功率和排障效率得到稳定验证。",
        }
    ],
    "a4_memory": [
        "回答结构：先结论，再说明约束、方案、权衡和验证结果。",
        "系统设计：明确容量、数据模型、一致性、容错、监控和降级。",
        "Agent 工程：工具参数校验、超时、重试、权限边界和评测闭环。",
        "项目复盘：区分事实、个人贡献、可量化结果和后续改进。",
    ],
}
