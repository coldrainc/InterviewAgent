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
