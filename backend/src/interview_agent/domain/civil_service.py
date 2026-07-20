from __future__ import annotations

from typing import Any


CIVIL_SERVICE_LEARNING_PLAN: list[dict[str, Any]] = [
    {
        "stage": "基础诊断",
        "title": "先测行测五大模块",
        "description": "用言语理解、数量关系、判断推理、资料分析、常识判断各 5-10 题建立正确率基线。",
        "tasks": ["记录每题耗时", "把错因分为知识点、方法、粗心、时间不足", "优先补资料分析和判断推理"],
    },
    {
        "stage": "模块训练",
        "title": "按题型拆解刷题",
        "description": "不要只按年份刷整卷，先按题型建立方法库，再做套卷限时。",
        "tasks": ["言语关注主旨、意图、逻辑填空", "判断推理关注图形、定义、类比、逻辑", "资料分析练速算和估算"],
    },
    {
        "stage": "申论提升",
        "title": "材料定位和规范表达",
        "description": "申论先练归纳概括、综合分析、提出对策，再练公文和大作文。",
        "tasks": ["答案必须回到材料依据", "训练分条作答和关键词前置", "积累公共治理表达"],
    },
    {
        "stage": "冲刺复盘",
        "title": "套卷限时和错题回炉",
        "description": "用历年卷或合法授权题源做限时训练，复盘比刷题数量更重要。",
        "tasks": ["每周至少一次限时套卷", "错题 24 小时内复做", "建立高频考点和易错方法清单"],
    },
]


CIVIL_SERVICE_SEED_QUESTIONS: list[dict[str, Any]] = [
    {
        "source": "built_in_sample",
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
