from __future__ import annotations

import os
from pathlib import Path
from typing import Any


# 本机调试时可通过环境变量指向本地资料目录；默认不依赖任何本机绝对路径，
# 资料链接使用内置知识库引用 key（kb://...），由前端映射到知识库文档。
INTERVIEW_CONTENT_ROOT = os.environ.get("INTERVIEW_CONTENT_ROOT", "").strip()


def doc(path: str) -> str:
    if INTERVIEW_CONTENT_ROOT:
        return Path(INTERVIEW_CONTENT_ROOT, path).as_uri()
    return f"kb://{path}"


DEFAULT_REVIEW_SITE: dict[str, Any] = {
    "plan": {
        "id": "cyh-14-day-interview-review",
        "title": "陈雨寒面试复习站",
        "subtitle": "14 天分阶段复习计划",
        "description": "把 Interview 目录里的简历、项目深挖、问答、公司专项和算法材料组织成可执行计划。",
        "commercial_positioning": [
            "可作为私有化交付的个人面试备考工作台模板",
            "计划、资料索引、题库、练习记录和进度持久化分离",
            "后续可扩展为多候选人、多岗位、多计划版本和团队训练营",
        ],
        "source_root": INTERVIEW_CONTENT_ROOT,
        "source_documents": [
            {"label": "14 天总计划", "url": doc("面试题/interview/00-面试分阶段复习总计划-14天版.md")},
            {"label": "自我介绍模板", "url": doc("面试题/interview/面试自我介绍模板.md")},
            {"label": "面试问答", "url": doc("面试题/interview/docs/interview_qna/面试问答.md")},
            {"label": "蚂蚁答题指南", "url": doc("面试题/interview/docs/job_targets/蚂蚁证券-AI-Native-前端答题指南.md")},
            {"label": "基础题 readme", "url": doc("面试题/readme.md")},
        ],
    },
    "phases": [
        {"id": "p1", "title": "基础储备", "range": "Day 1-3", "goal": "所有素材过一遍，简历上每个字能讲清楚。"},
        {"id": "p2", "title": "深挖对齐", "range": "Day 4-7", "goal": "每问必答，每答有行业对标。"},
        {"id": "p3", "title": "模拟冲刺", "range": "Day 8-11", "goal": "全真模拟、错题本清零、难点应答打磨。"},
        {"id": "p4", "title": "面试前速记", "range": "Day 12-14", "goal": "浓缩、记忆、状态管理，最后一天不学新东西。"},
    ],
    "days": [
        {
            "id": "day-1",
            "day": "Day 1",
            "phase": "p1",
            "title": "简历与自我介绍熟背",
            "tasks": [
                {"id": "day-1-resume-numbers", "title": "背两份简历所有数字，确保 70%+/30%+/40%+/50%-/25%- 口径一致", "tags": ["简历"], "docs": [{"label": "对外简历", "url": doc("面试题/interview/陈雨寒-全栈开发-对外.md")}, {"label": "对内简历", "url": doc("面试题/interview/陈雨寒-全栈开发-对内.md")}]},
                {"id": "day-1-intro-90", "title": "背自我介绍标准版 90 秒逐字稿，录音 2 遍", "tags": ["开场", "必做"], "critical": True, "docs": [{"label": "自我介绍模板", "url": doc("面试题/interview/面试自我介绍模板.md")}]},
                {"id": "day-1-intro-180", "title": "熟悉 3 分钟详述版框架，每个 STAR 四要素能口头讲", "tags": ["开场"], "docs": [{"label": "自我介绍模板", "url": doc("面试题/interview/面试自我介绍模板.md")}]},
                {"id": "day-1-js-network", "title": "JS/网络基础第一轮，通读 TCP/UDP、HTTP2、防抖节流、变量提升、CORS、手写题", "tags": ["基础"], "docs": [{"label": "基础题", "url": doc("面试题/readme.md")}]},
            ],
        },
        {
            "id": "day-2",
            "day": "Day 2",
            "phase": "p1",
            "title": "项目深挖 Part 1",
            "tasks": [
                {"id": "day-2-harmony", "title": "深挖鸿蒙 ArkUI + LiveView：生命周期竞态、状态机修复、Hybrid 容器 5 大 Service", "tags": ["鸿蒙"], "docs": [{"label": "鸿蒙深挖", "url": doc("面试题/interview/docs/resume_tech_deep/02-鸿蒙ArkUI与LiveView深挖.md")}]},
                {"id": "day-2-hybrid", "title": "深挖移动端 Hybrid：Lynx vs H5 取舍、容器降级策略、串房风险治理", "tags": ["跨端"], "docs": [{"label": "Hybrid 深挖", "url": doc("面试题/interview/docs/resume_tech_deep/03-移动端Hybrid与微前端深挖.md")}]},
                {"id": "day-2-agent-rag", "title": "深挖 Workflow Agent + RAG：三级 ID、TOML 损坏修复、双路召回 + Query Rewrite", "tags": ["AI"], "docs": [{"label": "AI Agent 深挖", "url": doc("面试题/interview/docs/resume_tech_deep/01-AI-Agent-RAG-MCP深挖.md")}]},
                {"id": "day-2-qna", "title": "面试问答 33 题过标题，打勾/打叉生成弱点清单", "tags": ["问答"], "docs": [{"label": "33 题", "url": doc("面试题/interview/docs/interview_qna/面试问答.md")}]},
                {"id": "day-2-wrong-book", "title": "基础第二轮：不会的题抄入错题本", "tags": ["基础"], "docs": [{"label": "基础题", "url": doc("面试题/readme.md")}]},
            ],
        },
        {
            "id": "day-3",
            "day": "Day 3",
            "phase": "p1",
            "title": "项目深挖 Part 2",
            "acceptance": "随机抽 6 大项目条目，每项不看资料讲 2 分钟 STAR。",
            "tasks": [
                {"id": "day-3-cross-platform", "title": "三大跨端差异对比：KMP/Lynx/RN 原理、复用率、生态、选型结论", "tags": ["跨端"], "docs": [{"label": "差异对比总览", "url": doc("面试题/interview/docs/cross_platform_interview_deep/01-三大跨端框架差异对比总览.md")}]},
                {"id": "day-3-kmp", "title": "KMP 深挖：共享层划分、大对象同步、Job 绑定生命周期修复故事", "tags": ["KMP"], "docs": [{"label": "KMP 深挖", "url": doc("面试题/interview/docs/cross_platform_interview_deep/02-KMP深挖-共享层与桥接通信.md")}]},
                {"id": "day-3-principles", "title": "KMP/Lynx/RN 三本原理通读，看结构和关键图", "tags": ["原理"], "docs": [{"label": "KMP", "url": doc("面试题/interview/docs/cross_platform_interview/01-KMP渲染与通信原理.md")}, {"label": "Lynx", "url": doc("面试题/interview/docs/cross_platform_interview/02-Lynx渲染与通信原理.md")}, {"label": "RN", "url": doc("面试题/interview/docs/cross_platform_interview/03-ReactNative渲染与通信原理.md")}]},
                {"id": "day-3-fullstack-runtime", "title": "Electron-NestJS 全栈 + Web Runtime 沙箱：IPC、包体积、沙箱策略", "tags": ["全栈"], "docs": [{"label": "Electron-NestJS", "url": doc("面试题/interview/docs/resume_tech_deep/04-Electron-NestJS全栈深挖.md")}, {"label": "Runtime 沙箱", "url": doc("面试题/interview/docs/resume_tech_deep/05-Web-Runtime沙箱深挖.md")}]},
                {"id": "day-3-difficulty", "title": "项目难点脑图四题：开播、短触、Hybrid、KMP，每个 4 要素背熟", "tags": ["STAR", "必做"], "critical": True, "docs": [{"label": "项目难点大纲", "url": doc("面试题/interview/interview_difficulty_mindmap.md")}]},
                {"id": "day-3-review", "title": "基础第三轮：错题本二刷", "tags": ["基础"], "docs": [{"label": "基础题", "url": doc("面试题/readme.md")}]},
            ],
        },
        {
            "id": "day-4",
            "day": "Day 4",
            "phase": "p2",
            "title": "Harness 选型与蚂蚁专项",
            "tasks": [
                {"id": "day-4-harness-selection", "title": "精读 Harness 01：8 方案定位、15 维对比关键结论、LangGraph/CrewAI/Dify 取舍", "tags": ["AI", "必做"], "critical": True, "docs": [{"label": "调研选型", "url": doc("面试题/interview/docs/harness_workflow/01-调研选型-8方案对比与决策树与面试话术.md")}]},
                {"id": "day-4-tradeoff", "title": "背融合方案 3 条 trade-off 原则和 8 个高频追问", "tags": ["选型话术"], "docs": [{"label": "15 追问", "url": doc("面试题/interview/docs/harness_workflow/01-调研选型-8方案对比与决策树与面试话术.md")}]},
                {"id": "day-4-ant-js", "title": "刷蚂蚁证券 AI Native JS：Fiber、虚拟 DOM、三数之和、loader/plugin、浏览器渲染", "tags": ["公司题"], "docs": [{"label": "蚂蚁算法", "url": doc("面试题/蚂蚁证券_AI_Native.js")}]},
                {"id": "day-4-ant-plan", "title": "蚂蚁准备计划 Day 1：岗位能力地图过一遍，把弱区标出来", "tags": ["蚂蚁"], "docs": [{"label": "蚂蚁准备计划", "url": doc("面试题/interview/docs/job_targets/蚂蚁证券-AI-Native-前端面试准备计划.md")}]},
            ],
        },
        {
            "id": "day-5",
            "day": "Day 5",
            "phase": "p2",
            "title": "Harness 落地与源码对标",
            "tasks": [
                {"id": "day-5-harness-design", "title": "读 Harness 02：六层架构、四大类 20+ 指标、门禁伪代码", "tags": ["架构"], "docs": [{"label": "设计方案", "url": doc("面试题/interview/docs/harness_workflow/02-设计方案-AI-Native工作流架构与Harness设计.md")}]},
                {"id": "day-5-harness-sla", "title": "读 Harness 03：容量、SLA、PITR、四级可观测、OnCall 和止血开关", "tags": ["生产落地"], "docs": [{"label": "落地手册", "url": doc("面试题/interview/docs/harness_workflow/03-落地手册-生产架构与SLA容灾与OnCall.md")}]},
                {"id": "day-5-source", "title": "源码学习 Day 1-3：Nano Claude Code types/prompts/agent/skills/approval", "tags": ["源码对标"], "docs": [{"label": "源码学习路线", "url": doc("面试题/interview/docs/harness_workflow/04-CodeAgent源码学习路线-配合面试复习.md")}]},
                {"id": "day-5-compare", "title": "写 1 页对比表：我的 Workflow Agent 设计 vs Nano Claude + Codex 一线实现", "tags": ["面试素材", "必做"], "critical": True, "docs": [{"label": "调研选型", "url": doc("面试题/interview/docs/harness_workflow/01-调研选型-8方案对比与决策树与面试话术.md")}]},
                {"id": "day-5-kuaishou", "title": "快手.js 全量过一遍", "tags": ["公司题"], "docs": [{"label": "快手题", "url": doc("面试题/快手.js")}]},
            ],
        },
        {
            "id": "day-6",
            "day": "Day 6",
            "phase": "p2",
            "title": "蚂蚁答题指南与详细话术",
            "tasks": [
                {"id": "day-6-ant-guide", "title": "背完蚂蚁 AI Native 答题指南 20+ 题：每题 30 秒主答 + 2 个关键词延伸", "tags": ["蚂蚁", "必做"], "critical": True, "docs": [{"label": "蚂蚁答题指南", "url": doc("面试题/interview/docs/job_targets/蚂蚁证券-AI-Native-前端答题指南.md")}]},
                {"id": "day-6-detailed-qna", "title": "精读详细话术 16 题：诊断、KMP、Hybrid、RAG、RN、LiveView、MCP、上下文", "tags": ["问答"], "docs": [{"label": "详细话术", "url": doc("面试题/interview/docs/interview_qna/面试问答-详细话术.md")}]},
                {"id": "day-6-star-stories", "title": "STAR 故事两条背熟：TOML 损坏、RAG 调优", "tags": ["STAR故事", "必做"], "critical": True, "docs": [{"label": "详细话术", "url": doc("面试题/interview/docs/interview_qna/面试问答-详细话术.md")}]},
                {"id": "day-6-algorithms", "title": "LeetCode 前端高频 10 道：LRU、深拷贝、Promise.all、防抖节流等", "tags": ["算法"], "docs": [{"label": "基础题", "url": doc("面试题/readme.md")}]},
            ],
        },
        {
            "id": "day-7",
            "day": "Day 7",
            "phase": "p2",
            "title": "源码学习收口与 1 小时模拟",
            "acceptance": "3 分钟 Harness 选型答辩版能讲完；蚂蚁/快手通过率 >= 70%；模拟命中率 >= 80%。",
            "tasks": [
                {"id": "day-7-memory-sandbox", "title": "源码学习 Day 4-6：Nano Memory/Git Worktree 与 Codex 三级平台沙箱", "tags": ["源码对标"], "docs": [{"label": "源码学习路线", "url": doc("面试题/interview/docs/harness_workflow/04-CodeAgent源码学习路线-配合面试复习.md")}]},
                {"id": "day-7-talk-track", "title": "重写新版 Workflow Agent 介绍话术，弱点清单每项写完 3 分钟回答", "tags": ["素材打磨", "必做"], "critical": True, "docs": [{"label": "自我介绍模板", "url": doc("面试题/interview/面试自我介绍模板.md")}, {"label": "详细话术", "url": doc("面试题/interview/docs/interview_qna/面试问答-详细话术.md")}]},
                {"id": "day-7-mock", "title": "周末 1 小时全真模拟：自我介绍、鸿蒙、Workflow Agent、Harness 选型，录音复盘", "tags": ["模拟", "必做"], "critical": True, "simulation": True, "docs": [{"label": "自我介绍", "url": doc("面试题/interview/面试自我介绍模板.md")}]},
            ],
        },
        {
            "id": "day-8",
            "day": "Day 8",
            "phase": "p3",
            "title": "全真模拟 1：大前端与跨端",
            "tasks": [
                {"id": "day-8-mock-cross", "title": "60 分钟模拟：LiveView、KMP、Hybrid、开播架构、RN 拆包、TCP/UDP、HTTP2、防抖节流、反向提问", "tags": ["模拟", "必做"], "critical": True, "simulation": True, "docs": [{"label": "鸿蒙深挖", "url": doc("面试题/interview/docs/resume_tech_deep/02-鸿蒙ArkUI与LiveView深挖.md")}, {"label": "跨端差异", "url": doc("面试题/interview/docs/cross_platform_interview_deep/01-三大跨端框架差异对比总览.md")}]},
                {"id": "day-8-algorithms", "title": "LeetCode 前端高频 10 道：数组/链表/树基础", "tags": ["算法"], "docs": [{"label": "基础题", "url": doc("面试题/readme.md")}]},
            ],
        },
        {
            "id": "day-9",
            "day": "Day 9",
            "phase": "p3",
            "title": "全真模拟 2：AI Native 与全栈",
            "tasks": [
                {"id": "day-9-mock-ai", "title": "60 分钟模拟：三级账本、融合方案、RAG 双路、入库流水线、Electron IPC、事件循环、LRU、Promise.all", "tags": ["模拟", "必做"], "critical": True, "simulation": True, "docs": [{"label": "Workflow Agent", "url": doc("面试题/interview/docs/resume_tech_deep/01-AI-Agent-RAG-MCP深挖.md")}, {"label": "Electron 全栈", "url": doc("面试题/interview/docs/resume_tech_deep/04-Electron-NestJS全栈深挖.md")}]},
                {"id": "day-9-algorithms", "title": "LeetCode 前端高频 10 道：字符串/DP/栈", "tags": ["算法"], "docs": [{"label": "基础题", "url": doc("面试题/readme.md")}]},
            ],
        },
        {
            "id": "day-10",
            "day": "Day 10",
            "phase": "p3",
            "title": "蚂蚁 90 分钟定制模拟",
            "tasks": [
                {"id": "day-10-ant-mock", "title": "90 分钟蚂蚁模拟：岗位匹配、Workflow 稳定性、三级沙箱、Gate、RAG 合规、答题指南抽题、Fiber 算法、反向提问", "tags": ["蚂蚁", "模拟", "必做"], "critical": True, "simulation": True, "docs": [{"label": "蚂蚁答题指南", "url": doc("面试题/interview/docs/job_targets/蚂蚁证券-AI-Native-前端答题指南.md")}, {"label": "蚂蚁准备计划", "url": doc("面试题/interview/docs/job_targets/蚂蚁证券-AI-Native-前端面试准备计划.md")}]},
                {"id": "day-10-questions", "title": "整理自己的 5 个反向提问问题库", "tags": ["反向"], "docs": [{"label": "自我介绍模板", "url": doc("面试题/interview/面试自我介绍模板.md")}]},
                {"id": "day-10-wrong-book", "title": "错题本补录 + 算法错题回做", "tags": ["算法"], "docs": [{"label": "蚂蚁算法", "url": doc("面试题/蚂蚁证券_AI_Native.js")}, {"label": "快手题", "url": doc("面试题/快手.js")}]},
            ],
        },
        {
            "id": "day-11",
            "day": "Day 11",
            "phase": "p3",
            "title": "快手/通用前端模拟",
            "acceptance": "4 场模拟均分 >= 7/10；错题本清零率 >= 90%；算法通过率 >= 75%。",
            "tasks": [
                {"id": "day-11-kuaishou-mock", "title": "60 分钟快手/通用前端面模拟", "tags": ["模拟"], "simulation": True, "docs": [{"label": "快手题", "url": doc("面试题/快手.js")}]},
                {"id": "day-11-promotion", "title": "晋升三板斧：3 个项目难点叙述练熟", "tags": ["STAR故事"], "docs": [{"label": "晋升三板斧", "url": doc("面试题/interview/promotion_speech_three_pillars.md")}]},
                {"id": "day-11-clear", "title": "错题本清零 >= 90%，Phase 1-3 所有错题回做", "tags": ["基础", "必做"], "critical": True, "docs": [{"label": "基础题", "url": doc("面试题/readme.md")}]},
                {"id": "day-11-algorithms", "title": "算法总刷：readme 手写题 + 快手.js + 蚂蚁错题", "tags": ["算法", "必做"], "critical": True, "docs": [{"label": "基础", "url": doc("面试题/readme.md")}, {"label": "快手", "url": doc("面试题/快手.js")}, {"label": "蚂蚁算法", "url": doc("面试题/蚂蚁证券_AI_Native.js")}]},
            ],
        },
        {
            "id": "day-12",
            "day": "Day 12",
            "phase": "p4",
            "title": "制作 A4 速记单",
            "tasks": [
                {"id": "day-12-a4-a", "title": "A 面：6 项目 STAR 卡，每项 4 要素 3 行写清楚", "tags": ["A4", "必做"], "critical": True},
                {"id": "day-12-a4-b", "title": "B 面：Harness 8 条、跨端一句话、高频 JS/网络 10 句、3 个 STAR 故事", "tags": ["A4", "必做"], "critical": True},
            ],
        },
        {
            "id": "day-13",
            "day": "Day 13",
            "phase": "p4",
            "title": "按公司定制",
            "tasks": [
                {"id": "day-13-ant", "title": "蚂蚁面：重看准备计划、答题指南、蚂蚁算法错题和岗位匹配段", "tags": ["定制"], "docs": [{"label": "蚂蚁准备计划", "url": doc("面试题/interview/docs/job_targets/蚂蚁证券-AI-Native-前端面试准备计划.md")}, {"label": "答题指南", "url": doc("面试题/interview/docs/job_targets/蚂蚁证券-AI-Native-前端答题指南.md")}, {"label": "蚂蚁算法", "url": doc("面试题/蚂蚁证券_AI_Native.js")}]},
                {"id": "day-13-general", "title": "通用面：快手.js、readme 错题二刷、Harness 选型三原则背一遍", "tags": ["定制"], "docs": [{"label": "快手题", "url": doc("面试题/快手.js")}, {"label": "基础", "url": doc("面试题/readme.md")}]},
                {"id": "day-13-only-wrong", "title": "算法只刷错题本，不刷新题", "tags": ["算法", "必做"], "critical": True},
            ],
        },
        {
            "id": "day-14",
            "day": "Day 14",
            "phase": "p4",
            "title": "面试前最后一天",
            "tasks": [
                {"id": "day-14-a4", "title": "A4 速记单过 2 遍", "tags": ["速记", "必做"], "critical": True},
                {"id": "day-14-intro", "title": "自我介绍标准版 90 秒录一遍音", "tags": ["开场"]},
                {"id": "day-14-questions", "title": "反向提问问题库过 1 遍", "tags": ["反向"]},
                {"id": "day-14-rest", "title": "散步/运动/早睡，状态比多刷题重要", "tags": ["心理", "必做"], "critical": True},
                {"id": "day-14-ready", "title": "准备简历 2 份打印版、笔、水杯、面试链接和安静房间", "tags": ["准备"]},
            ],
        },
    ],
    "intro_scripts": [
        {"id": "intro-30", "label": "电梯版", "duration_seconds": 30, "scenario": "HR/电话面", "text": "你好，我叫陈雨寒，28 岁，6 年前端与全栈经验。最近在抖音直播做前端开发，核心方向两个：一是鸿蒙端 0-1 建设和 KMP 跨端共享，二是 AI Agent Workflow 全链路诊断 + RAG 知识库建设。之前在网易云音乐做直播的 RN 和工程化，主导过赤兔元框架和海豚组件平台。很高兴有这次机会。"},
        {"id": "intro-90", "label": "标准版", "duration_seconds": 90, "scenario": "技术一面默认", "text": "你好，我是陈雨寒，江西财经大学软件工程 20 届，6 年前端与全栈开发经验，求职方向全栈或 AI 应用开发。最近两年半我在抖音直播做前端，主要做跨端和 AI 应用两块：跨端方向参与抖音直播鸿蒙端 0-1 建设，并主导 KMP 跨端方案，覆盖鸿蒙/安卓/iOS 三端；AI 应用方向参与 Workflow Agent 智能体平台建设，负责全链路诊断与问题排查能力开发，也参与直播业务 RAG 知识库建设。之前四年在网易云音乐做直播，覆盖 RN/H5 Hybrid 海内外，主导赤兔元框架改造和海豚组件平台。技术上我比较有深度的三个方向是跨平台工程、AI Agent 可观测与评测、前端工程化治理。"},
        {"id": "intro-ant", "label": "蚂蚁岗位匹配段", "duration_seconds": 30, "scenario": "蚂蚁证券 AI Native", "text": "我之所以对这个机会特别感兴趣，是因为你们做 AI Native 全栈应用这件事，和我在抖音做 Workflow Agent + RAG 知识库的方向高度一致。我在 Agent 执行可观测、异常归因、RAG 事实约束这几块已经踩过一年多实坑，对怎么把 AI 功能做成工程上可信、可测、可回滚的产品有比较成型的方法论。"},
    ],
    "star_cards": [
        {"id": "star-harmony", "title": "鸿蒙直播端 0-1 建设", "tag": "鸿蒙", "background": "抖音直播要在鸿蒙端快速拉齐安卓/iOS 能力。", "challenge": "多端逻辑重复，LiveView 等强交互必须原生，成熟活动要快速接入。", "solution": "落地 H5/Lynx 混合架构，特色能力走原生 ArkTS，LiveView 竞态用状态机修复。", "result": "鸿蒙业务 1 个月 MVP 上线，新业务平均接入时间从 5 人日降到 2 人日。"},
        {"id": "star-kmp", "title": "KMP 跨端三端共享", "tag": "KMP", "background": "互动功能安卓/鸿蒙/iOS 三份重复实现。", "challenge": "共享边界、大对象同步、跨语言异步回调生命周期不一致。", "solution": "公共逻辑下沉 commonMain，批量传输，Job 绑定宿主生命周期。", "result": "代码复用率 70%+，通信效率 +30%，迁移成本 -50%。"},
        {"id": "star-agent", "title": "Workflow Agent 全链路诊断", "tag": "AI Agent", "background": "Agent 上线后 Prompt/工具变更缺少可回放证据。", "challenge": "需要定位 LLM/工具/沙箱/会话根因，修复 TOML 损坏。", "solution": "traceId/spanId/agentRunId 三级串联，Runtime Trace + 阶段账本，SHA-256 原子替换与回滚。", "result": "异常定位从半天降到 30 分钟内，TOML 损坏类事故清零。"},
        {"id": "star-rag", "title": "直播业务 RAG 知识库", "tag": "RAG", "background": "直播业务规则复杂，新人口径不一致，Agent 容易幻觉。", "challenge": "长术语召回、口语 Query 和多轮上下文幻觉。", "solution": "向量 + BM25 双路召回、RRF 融合、Query Rewrite、MCP Skill 事实约束。", "result": "Top-1 召回率 +18%，人工抽检一致率 +22%。"},
        {"id": "star-engineering", "title": "赤兔元工程框架 + 海豚组件平台", "tag": "工程化", "background": "网易直播 RN/H5 多业务巨石框架和组件重复维护。", "challenge": "RN 包体大、H5 配置散、组件维护成本高。", "solution": "RN 拆包、Webpack5 持久化缓存、多进程压缩、RN 到 Web 兼容层和 Token 模块化。", "result": "RN 构建效率 +40%，H5 打包从 5 分钟降到 1 分钟内，维护成本 -25%。"},
        {"id": "star-fullstack", "title": "跨境 ERP Electron + NestJS 全栈", "tag": "全栈", "background": "跨境运营后台需要桌面客户端、本地服务、离线缓存和云端同步。", "challenge": "IPC 容易混乱、安装包体积大、本地云端一致性。", "solution": "Electron + NestJS 本地后端，IPC 按命名空间路由，electron-builder 分平台打包。", "result": "可独立交付桌面客户端，包体 120MB，离线同步一致性 99.9%。"},
    ],
    "a4_memory": [
        "LangGraph 排第一：显式状态机、Checkpoint、HITL、LangSmith 可观测。",
        "自研 Runtime 是稳定资产，LangGraph 适合双轨灰度，不激进替换。",
        "门禁三件套：Scenario 版本化用例、Baseline 历史锚点、Gate 规则。",
        "P0 止血：GATE_ENABLED=false，DEFERRED_LLM_AS_PASS=true。",
        "KMP = 逻辑跨平台 + 原生 UI；Lynx = 活动发版快；RN = React 生态大。",
        "KMP 通信三招：批量减次数、Job 绑定生命周期、大对象只传 id 懒拉取。",
        "RN 新架构：JSI、Fabric、TurboModule。",
        "TCP 可靠按序，UDP 低开销；HTTP2 多路复用 + HPACK。",
        "debounce 取最后一次，throttle 取固定窗口内的第一次或一次。",
        "三个 STAR 故事：LiveView 竞态、TOML 损坏、RAG 召回低。",
    ],
}
