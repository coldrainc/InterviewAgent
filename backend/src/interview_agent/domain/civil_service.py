from __future__ import annotations

from typing import Any


CIVIL_SERVICE_LEARNING_PLAN: list[dict[str, Any]] = [
    {
        "stage": "基础诊断",
        "title": "先确定训练类型和能力短板",
        "description": "把目标拆成面试表达、知识点刷题、真题复盘三个层面，先建立正确率和回答质量基线。",
        "tasks": ["选择训练类型：互联网、AI 工程、考公等", "记录每题耗时和错因", "把错因分为知识点、表达、方法、时间不足"],
    },
    {
        "stage": "模块训练",
        "title": "按题型建立方法库",
        "description": "互联网和 AI 工程可以按项目深挖、系统设计、算法、RAG/Agent、行为面试拆；考公可以按行测、申论、结构化面试拆。",
        "tasks": ["每类题沉淀答题模板", "把高频知识点做成错题集", "同一题型连续练到稳定再切换"],
    },
    {
        "stage": "表达提升",
        "title": "从会做到会讲",
        "description": "刷题不是终点，最终要把答案组织成面试能听懂、能追问、能验证的表达。",
        "tasks": ["先讲结论，再讲依据", "训练分条作答和关键词前置", "每次复盘都补充一个具体案例或指标"],
    },
    {
        "stage": "冲刺复盘",
        "title": "限时训练和错题回炉",
        "description": "使用自有题库、历年真题或合法授权题源做限时训练，复盘比刷题数量更重要。",
        "tasks": ["每周至少一次限时训练", "错题 24 小时内复做", "建立高频考点和易错方法清单"],
    },
]


CIVIL_SERVICE_SEED_QUESTIONS: list[dict[str, Any]] = [
    {
        "source": "built_in_sample",
        "practice_category": "civil_service",
        "exam_year": 2026,
        "exam_name": "考公行测训练样题",
        "subject": "xingce",
        "question_type": "言语理解",
        "prompt": "某地推进政务服务数字化改革，材料强调既要让群众少跑腿，也要避免老年群体因不会使用智能设备而办事困难。最适合概括该材料主旨的是：",
        "choices": ["数字化改革应追求技术领先", "政务服务要兼顾效率与包容性", "老年群体不适合使用线上服务", "线下窗口会降低行政效率"],
        "answer": "B",
        "explanation": "材料同时强调少跑腿和避免数字鸿沟，核心是效率与包容并重。",
        "difficulty": "easy",
        "tags": ["政务服务", "主旨概括", "数字鸿沟"],
    },
    {
        "source": "built_in_sample",
        "practice_category": "civil_service",
        "exam_year": 2026,
        "exam_name": "考公行测训练样题",
        "subject": "xingce",
        "question_type": "判断推理",
        "prompt": "所有基层治理创新都需要群众参与。有些数字治理项目属于基层治理创新。据此可以推出：",
        "choices": ["所有数字治理项目都需要群众参与", "有些数字治理项目需要群众参与", "没有群众参与就没有数字治理", "基层治理创新都属于数字治理项目"],
        "answer": "B",
        "explanation": "有些数字治理项目属于基层治理创新，而所有基层治理创新都需要群众参与，因此有些数字治理项目需要群众参与。",
        "difficulty": "medium",
        "tags": ["逻辑判断", "三段论", "基层治理"],
    },
    {
        "source": "built_in_sample",
        "practice_category": "civil_service",
        "exam_year": 2026,
        "exam_name": "考公申论训练样题",
        "subject": "shenlun",
        "question_type": "归纳概括",
        "prompt": "请根据给定材料，概括某县推进乡村公共服务均等化的主要做法。要求：全面、准确、有条理，不超过 200 字。",
        "choices": [],
        "answer": "从基础设施、服务下沉、数字平台、群众参与、长效机制等方面概括。",
        "explanation": "申论概括题要紧扣材料，按同类合并原则提炼关键词，并避免脱离材料发挥。",
        "difficulty": "medium",
        "tags": ["申论", "归纳概括", "公共服务"],
    },
]


INTERNET_SEED_QUESTIONS: list[dict[str, Any]] = [
    {
        "source": "built_in_sample",
        "practice_category": "internet",
        "exam_year": 2026,
        "exam_name": "互联网技术面试训练样题",
        "subject": "system_design",
        "question_type": "系统设计",
        "prompt": "设计一个短链服务。请说明核心表结构、生成算法、跳转链路、缓存策略、风控和高并发下的可用性设计。",
        "choices": [],
        "answer": "围绕短码生成、唯一性、重定向读多写少、缓存、限流、黑名单、监控和降级展开。",
        "explanation": "系统设计题重点不是背方案，而是讲清楚业务约束、核心路径、数据模型、容量估算和故障处理。",
        "difficulty": "medium",
        "tags": ["系统设计", "高并发", "缓存", "风控"],
    },
    {
        "source": "built_in_sample",
        "practice_category": "internet",
        "exam_year": 2026,
        "exam_name": "互联网技术面试训练样题",
        "subject": "project",
        "question_type": "项目深挖",
        "prompt": "请用 STAR 结构讲一个你主导排查线上故障的案例，重点说明定位路径、数据证据、止血动作和复盘改进。",
        "choices": [],
        "answer": "需要覆盖背景、任务、行动、结果，并补充监控指标、日志证据、回滚/降级和后续机制建设。",
        "explanation": "项目深挖题要体现真实工程经验，回答里最好有指标、个人职责、关键判断和复盘闭环。",
        "difficulty": "medium",
        "tags": ["项目深挖", "线上故障", "稳定性", "STAR"],
    },
]


AI_ENGINEERING_SEED_QUESTIONS: list[dict[str, Any]] = [
    {
        "source": "built_in_sample",
        "practice_category": "ai_engineering",
        "exam_year": 2026,
        "exam_name": "AI 工程面试训练样题",
        "subject": "project",
        "question_type": "RAG 项目深挖",
        "prompt": "你做过的 RAG 系统如何处理召回不准和幻觉问题？请说明切分、向量召回、重排、引用校验、评测指标和线上观测。",
        "choices": [],
        "answer": "可从 chunk 策略、混合检索、rerank、答案引用、拒答机制、离线评测集、线上反馈闭环等角度回答。",
        "explanation": "AI 工程题要避免只讲概念，需要落到数据、评测、上线和安全治理。",
        "difficulty": "hard",
        "tags": ["RAG", "召回", "评测", "幻觉治理"],
    },
    {
        "source": "built_in_sample",
        "practice_category": "ai_engineering",
        "exam_year": 2026,
        "exam_name": "AI 工程面试训练样题",
        "subject": "system_design",
        "question_type": "Agent 设计",
        "prompt": "如果要设计一个可调用工具的 Agent，你会如何做权限控制、工具选择、失败重试、成本控制和审计日志？",
        "choices": [],
        "answer": "重点覆盖工具白名单、参数校验、最小权限、计划执行、超时重试、预算上限、人工确认和全链路审计。",
        "explanation": "Agent 不是只让模型调用函数，还要把安全边界、可观测性和成本治理设计进去。",
        "difficulty": "hard",
        "tags": ["Agent", "工具调用", "权限", "审计"],
    },
]


DEFAULT_PRACTICE_QUESTIONS: list[dict[str, Any]] = [
    *INTERNET_SEED_QUESTIONS,
    *AI_ENGINEERING_SEED_QUESTIONS,
    *CIVIL_SERVICE_SEED_QUESTIONS,
]
