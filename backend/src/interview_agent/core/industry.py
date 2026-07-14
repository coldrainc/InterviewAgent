from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Industry(str, Enum):
    INTERNET = "internet"
    AI_APPLICATION = "ai_application"
    ECOMMERCE = "ecommerce"
    FINTECH = "fintech"
    ENTERPRISE_SAAS = "enterprise_saas"


class IndustryProfile(BaseModel):
    value: Industry
    label: str
    description: str
    scenario_keywords: list[str] = Field(default_factory=list)
    interview_focus: list[str] = Field(default_factory=list)
    production_signals: list[str] = Field(default_factory=list)
    risk_controls: list[str] = Field(default_factory=list)
    follow_up_angles: list[str] = Field(default_factory=list)
    answer_expectations: list[str] = Field(default_factory=list)

    def to_prompt_block(self) -> str:
        return "\n".join(
            [
                f"行业定位：{self.label}",
                f"业务场景：{self.description}",
                f"常见场景关键词：{_join(self.scenario_keywords)}",
                f"面试关注点：{_join(self.interview_focus)}",
                f"生产化信号：{_join(self.production_signals)}",
                f"风险与治理：{_join(self.risk_controls)}",
                f"追问角度：{_join(self.follow_up_angles)}",
                f"高分回答期待：{_join(self.answer_expectations)}",
            ]
        )

    def option_payload(self, target_role: str = "AI 应用工程师") -> dict[str, Any]:
        return {
            "value": self.value.value,
            "label": self.label,
            "description": self.description,
            "scenario_keywords": self.scenario_keywords,
            "interview_focus": self.interview_focus,
            "production_signals": self.production_signals,
            "risk_controls": self.risk_controls,
            "follow_up_angles": self.follow_up_angles,
            "answer_expectations": self.answer_expectations,
            "recommended_focus_areas": recommended_focus_areas(self.value, target_role),
        }


INDUSTRY_PROFILES: dict[Industry, IndustryProfile] = {
    Industry.INTERNET: IndustryProfile(
        value=Industry.INTERNET,
        label="互联网行业",
        description="面向高并发用户产品、内容/直播/社区/工具类业务，强调体验、增长、效率和快速迭代。",
        scenario_keywords=["高并发", "低延迟", "灰度发布", "增长指标", "内容安全", "多端体验"],
        interview_focus=[
            "简历项目真实性和个人 ownership",
            "RAG / Agent 在用户产品中的体验闭环",
            "高并发、缓存、降级和成本控制",
            "A/B 实验、埋点、监控告警和事故复盘",
        ],
        production_signals=["p95/p99 延迟", "QPS", "召回率", "转化率", "灰度通过率", "成本/千次调用"],
        risk_controls=["权限隔离", "内容安全", "Prompt 注入", "数据脱敏", "兜底降级"],
        follow_up_angles=[
            "如果用户量放大 10 倍，瓶颈在哪里",
            "如何证明 AI 能力真的带来业务收益",
            "线上 badcase 如何发现、归因和修复",
        ],
        answer_expectations=[
            "能讲清业务目标、技术链路和个人决策",
            "能用指标验证效果而不是只说体验更好",
            "能覆盖灰度、回滚、监控和成本治理",
        ],
    ),
    Industry.AI_APPLICATION: IndustryProfile(
        value=Industry.AI_APPLICATION,
        label="AI 应用 / 大模型",
        description="面向 Agent、RAG、LLMOps、AI Copilot 和行业知识助手，强调可靠性、评测、工具调用和安全边界。",
        scenario_keywords=["RAG", "Agent", "工具调用", "LLMOps", "评测集", "可观测性"],
        interview_focus=[
            "AgentLoop、状态机和工具编排设计",
            "RAG 检索、重排、引用、权限和增量索引",
            "离线评测、在线评测、回归集和人工反馈闭环",
            "模型降级、多模型路由、token 成本和安全护栏",
        ],
        production_signals=["忠实度", "答案相关性", "检索命中率", "工具成功率", "幻觉率", "token 成本"],
        risk_controls=["Prompt 注入", "越权检索", "敏感信息泄露", "工具误调用", "模型漂移"],
        follow_up_angles=[
            "如何设计可复现的 RAG/Agent 评测 Harness",
            "如何处理检索到了但模型答错的问题",
            "如何定义 Agent 工具调用的失败、重试和补偿",
        ],
        answer_expectations=[
            "能区分召回问题、生成问题和工具执行问题",
            "能说明评测集、指标、阈值和上线门禁",
            "能讲出观测链路和安全边界",
        ],
    ),
    Industry.ECOMMERCE: IndustryProfile(
        value=Industry.ECOMMERCE,
        label="电商 / 本地生活",
        description="面向搜索推荐、导购客服、商家运营和交易链路，强调转化、库存、营销、履约和风控。",
        scenario_keywords=["商品搜索", "智能导购", "客服助手", "推荐排序", "库存价格", "履约售后"],
        interview_focus=[
            "AI 导购/客服的意图识别、知识 grounding 和交易转化",
            "商品、价格、库存等实时数据与 RAG 的融合",
            "推荐/搜索质量、实验指标和链路稳定性",
            "风控、合规话术、售后责任和商家数据隔离",
        ],
        production_signals=["CTR", "CVR", "GMV", "客诉率", "转人工率", "订单履约错误率"],
        risk_controls=["价格误导", "库存过期", "虚假承诺", "商家数据隔离", "营销合规"],
        follow_up_angles=[
            "如何避免模型编造价格、库存和活动规则",
            "AI 答案影响交易决策时如何做风控",
            "如何用实验判断 AI 导购是否真实提升转化",
        ],
        answer_expectations=[
            "能把 RAG 与实时业务数据区分清楚",
            "能覆盖转人工、兜底话术和交易安全",
            "能从业务指标和工程指标双向验证",
        ],
    ),
    Industry.FINTECH: IndustryProfile(
        value=Industry.FINTECH,
        label="金融科技",
        description="面向金融投研、风控、合规、客服和运营自动化，强调审计、权限、可解释和高可靠。",
        scenario_keywords=["风控", "投研", "合规", "审计", "权限", "可解释性"],
        interview_focus=[
            "金融知识库的来源可信、版本管理和引用证据",
            "权限隔离、数据脱敏、审计日志和合规留痕",
            "模型输出的保守性、免责声明和人工复核",
            "高可用、灾备、回滚和错误责任边界",
        ],
        production_signals=["准确率", "召回率", "误报率", "审计覆盖率", "SLA", "人工复核通过率"],
        risk_controls=["投资建议风险", "敏感数据泄露", "越权访问", "不可解释决策", "监管合规"],
        follow_up_angles=[
            "如何证明回答依据来自可信来源",
            "如何处理模型输出可能影响用户资金决策",
            "如何设计审计日志和人工复核流程",
        ],
        answer_expectations=[
            "能明确 AI 不能直接替代合规和最终决策",
            "能讲清权限、审计、复核和留痕",
            "能用保守策略处理高风险输出",
        ],
    ),
    Industry.ENTERPRISE_SAAS: IndustryProfile(
        value=Industry.ENTERPRISE_SAAS,
        label="企业 SaaS / ToB",
        description="面向企业知识库、办公协作、CRM/ERP/工单等工作流，强调多租户、权限、集成和可运营。",
        scenario_keywords=["多租户", "RBAC", "企业知识库", "工作流", "审计", "系统集成"],
        interview_focus=[
            "企业知识权限、租户隔离和数据生命周期",
            "Agent 与第三方系统/API 的工具调用边界",
            "管理员配置、可观测、计费和用量治理",
            "私有化部署、数据合规和客户成功闭环",
        ],
        production_signals=["租户隔离通过率", "SLA", "工具调用成功率", "工单解决率", "活跃率", "续费风险"],
        risk_controls=["跨租户泄露", "工具误操作", "权限过大", "审计缺失", "私有化运维复杂度"],
        follow_up_angles=[
            "如何保证 RAG 不返回用户无权访问的文档",
            "Agent 执行业务动作前如何做确认和回滚",
            "如何面向企业管理员提供可配置和可审计能力",
        ],
        answer_expectations=[
            "能把多租户、权限和审计作为一等公民",
            "能说明集成系统的失败补偿和人工确认",
            "能关注客户交付、运维和成本模型",
        ],
    ),
}


INDUSTRY_LABELS = {industry: profile.label for industry, profile in INDUSTRY_PROFILES.items()}


def get_industry_profile(industry: Industry | str) -> IndustryProfile:
    parsed = industry if isinstance(industry, Industry) else Industry(industry)
    return INDUSTRY_PROFILES[parsed]


def industry_options(target_role: str = "AI 应用工程师") -> list[dict[str, Any]]:
    return [profile.option_payload(target_role) for profile in INDUSTRY_PROFILES.values()]


def recommended_focus_areas(industry: Industry | str, target_role: str = "AI 应用工程师") -> list[str]:
    profile = get_industry_profile(industry)
    return [
        f"{profile.label}简历项目真实性深挖",
        f"{profile.label}{target_role}核心能力",
        *profile.interview_focus[:3],
        "评测、上线、安全、观测与成本治理",
        "行为协作、项目复盘和影响力",
    ]


def _join(values: list[str]) -> str:
    return "、".join(values) if values else "暂无"
