from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
import math
import re


MICROS_PER_CREDIT = 1_000_000
USD_TO_CREDITS = Decimal("100")
DEFAULT_TRIAL_USES = 2
DEFAULT_CHAT_MODEL = "gpt-5.5"


@dataclass(frozen=True)
class ModelPricing:
    id: str
    provider: str
    display_name: str
    input_usd_per_1m: Decimal
    output_usd_per_1m: Decimal
    context_window: int | None = None
    enabled: bool = True
    notes: str = ""
    category: str = "通用模型"

    @property
    def input_credits_per_1m(self) -> Decimal:
        return self.input_usd_per_1m * USD_TO_CREDITS

    @property
    def output_credits_per_1m(self) -> Decimal:
        return self.output_usd_per_1m * USD_TO_CREDITS


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class UsageCharge:
    model: ModelPricing
    usage: TokenUsage
    credits_micros: int
    trial_used: bool = False

    @property
    def credits(self) -> Decimal:
        return Decimal(self.credits_micros) / Decimal(MICROS_PER_CREDIT)


def default_model_catalog() -> dict[str, ModelPricing]:
    """Default public model catalog.

    Prices are operational defaults and should be periodically reconciled with
    provider pricing pages before production launch.
    """

    models = [
        ModelPricing(
            "gpt-5.5",
            "openai",
            "OpenAI GPT-5.5",
            Decimal("5.00"),
            Decimal("30.00"),
            1050000,
            notes="最新通用/推理默认模型；长上下文会触发更高计费，请按官方价格页定期校准。",
            category="默认通用",
        ),
        ModelPricing(
            "gpt-5.5-pro",
            "openai",
            "OpenAI GPT-5.5 Pro",
            Decimal("30.00"),
            Decimal("180.00"),
            1050000,
            notes="高质量深度推理模型，建议用于高价值面试评估和复杂项目深挖。",
            category="最高质量",
        ),
        ModelPricing("gpt-5.4", "openai", "OpenAI GPT-5.4", Decimal("2.50"), Decimal("15.00"), 1050000, enabled=False, notes="历史兼容模型；新会话建议优先选择 GPT-5.5。"),
        ModelPricing(
            "gpt-5.4-mini",
            "openai",
            "OpenAI GPT-5.4 mini",
            Decimal("0.75"),
            Decimal("4.50"),
            notes="轻量生产模型，适合默认降本或高并发场景。",
            category="高性价比",
        ),
        ModelPricing(
            "gpt-5.4-nano",
            "openai",
            "OpenAI GPT-5.4 nano",
            Decimal("0.20"),
            Decimal("1.25"),
            enabled=False,
            notes="高吞吐低成本模型，适合分类、摘要和简单问答。",
        ),
        ModelPricing(
            "gpt-4.1-nano",
            "openai",
            "OpenAI GPT-4.1 nano",
            Decimal("0.10"),
            Decimal("0.40"),
            1047576,
            enabled=False,
            notes="低成本非推理模型。",
        ),
        ModelPricing("gpt-4o-mini", "openai", "OpenAI GPT-4o mini", Decimal("0.15"), Decimal("0.60"), 128000, enabled=False, notes="历史兼容模型；新会话建议优先选择 GPT-5.4 mini。"),
        ModelPricing("gpt-4.1-mini", "openai", "OpenAI GPT-4.1 mini", Decimal("0.40"), Decimal("1.60"), 1047576, enabled=False, notes="历史兼容模型；新会话建议优先选择 GPT-5.4 mini。"),
        ModelPricing("gpt-4.1", "openai", "OpenAI GPT-4.1", Decimal("2.00"), Decimal("8.00"), 1047576, enabled=False, notes="历史兼容模型；新会话建议优先选择 GPT-5.5。"),
        ModelPricing(
            "claude-fable-5",
            "anthropic",
            "Claude Fable 5",
            Decimal("10.00"),
            Decimal("50.00"),
            1000000,
            notes="Anthropic 原生适配器调用，需要配置 ANTHROPIC_API_KEY。",
            category="长上下文深度分析",
        ),
        ModelPricing(
            "claude-opus-4-8",
            "anthropic",
            "Claude Opus 4.8",
            Decimal("5.00"),
            Decimal("25.00"),
            1000000,
            enabled=False,
            notes="Anthropic 原生适配器调用，需要配置 ANTHROPIC_API_KEY。",
        ),
        ModelPricing(
            "claude-sonnet-5",
            "anthropic",
            "Claude Sonnet 5",
            Decimal("3.00"),
            Decimal("15.00"),
            1000000,
            enabled=False,
            notes="Anthropic 原生适配器调用，需要配置 ANTHROPIC_API_KEY。",
        ),
        ModelPricing(
            "claude-haiku-4-5",
            "anthropic",
            "Claude Haiku 4.5",
            Decimal("1.00"),
            Decimal("5.00"),
            200000,
            enabled=False,
            notes="Anthropic 原生适配器调用，需要配置 ANTHROPIC_API_KEY。",
        ),
        ModelPricing(
            "claude-opus-4-1",
            "anthropic",
            "Claude Opus 4.1",
            Decimal("15.00"),
            Decimal("75.00"),
            200000,
            enabled=False,
            notes="历史兼容模型；新会话建议优先选择 Claude Fable 5、Opus 4.8 或 Sonnet 5。",
        ),
        ModelPricing(
            "claude-sonnet-4-5",
            "anthropic",
            "Claude Sonnet 4.5",
            Decimal("3.00"),
            Decimal("15.00"),
            200000,
            enabled=False,
            notes="历史兼容模型；新会话建议优先选择 Claude Sonnet 5。",
        ),
        ModelPricing("claude-3-5-haiku-latest", "anthropic", "Claude 3.5 Haiku", Decimal("0.80"), Decimal("4.00"), 200000, enabled=False, notes="历史兼容模型；新会话建议优先选择 Claude Fable 5。"),
        ModelPricing("claude-sonnet-4", "anthropic", "Claude Sonnet 4", Decimal("3.00"), Decimal("15.00"), 200000, enabled=False, notes="历史兼容模型；新会话建议优先选择 Claude Fable 5。"),
        ModelPricing(
            "gemini-3.5-flash",
            "google",
            "Gemini 3.5 Flash",
            Decimal("1.50"),
            Decimal("9.00"),
            1000000,
            notes="通过 Gemini OpenAI-compatible endpoint 调用，需要 GEMINI_API_KEY 或 GOOGLE_API_KEY。",
            category="多模态低延迟",
        ),
        ModelPricing(
            "gemini-3.1-pro",
            "google",
            "Gemini 3.1 Pro",
            Decimal("2.00"),
            Decimal("12.00"),
            2000000,
            enabled=False,
            notes="通过 Gemini OpenAI-compatible endpoint 调用，需要 GEMINI_API_KEY 或 GOOGLE_API_KEY；生产请按上下文长度阶梯价校准。",
        ),
        ModelPricing(
            "gemini-3.1-flash-lite",
            "google",
            "Gemini 3.1 Flash Lite",
            Decimal("0.25"),
            Decimal("1.50"),
            1000000,
            enabled=False,
            notes="通过 Gemini OpenAI-compatible endpoint 调用，需要 GEMINI_API_KEY 或 GOOGLE_API_KEY；预览/阶梯价请以上线账单为准。",
        ),
        ModelPricing("gemini-2.5-flash", "google", "Gemini 2.5 Flash", Decimal("0.30"), Decimal("2.50"), 1000000, enabled=False, notes="历史兼容模型；新会话建议优先选择 Gemini 3.5 Flash。"),
        ModelPricing("gemini-2.5-pro", "google", "Gemini 2.5 Pro", Decimal("1.25"), Decimal("10.00"), 2000000, enabled=False, notes="历史兼容模型；新会话建议优先选择 Gemini 3.5 Flash。"),
        ModelPricing("gemini-1.5-flash", "google", "Gemini 1.5 Flash", Decimal("0.075"), Decimal("0.30"), 1000000, enabled=False, notes="历史兼容模型；新会话建议优先选择 Gemini 3.5 Flash。"),
        ModelPricing("gemini-1.5-pro", "google", "Gemini 1.5 Pro", Decimal("1.25"), Decimal("5.00"), 2000000, enabled=False, notes="历史兼容模型；新会话建议优先选择 Gemini 3.5 Flash。"),
        ModelPricing(
            "deepseek-v4-pro",
            "deepseek",
            "DeepSeek V4 Pro",
            Decimal("0.44"),
            Decimal("0.88"),
            1000000,
            notes="DeepSeek V4 高能力模型；价格按运营默认值估算，请以官方账单校准。",
            category="高性价比推理",
        ),
        ModelPricing("deepseek-v4-flash", "deepseek", "DeepSeek V4 Flash", Decimal("0.14"), Decimal("0.56"), 1000000, enabled=False, notes="内部降本备选；默认产品清单只展示 DeepSeek V4 Pro。"),
        ModelPricing(
            "deepseek-chat",
            "deepseek",
            "DeepSeek Chat",
            Decimal("0.27"),
            Decimal("1.10"),
            64000,
            enabled=False,
            notes="旧别名，DeepSeek 官方公告称 2026-07-24 后将不可用。",
        ),
        ModelPricing(
            "deepseek-reasoner",
            "deepseek",
            "DeepSeek Reasoner",
            Decimal("0.55"),
            Decimal("2.19"),
            64000,
            enabled=False,
            notes="旧别名，DeepSeek 官方公告称 2026-07-24 后将不可用。",
        ),
        ModelPricing("qwen3.7-max", "alibaba", "Qwen3.7 Max", Decimal("2.50"), Decimal("7.50"), 1000000, category="中文企业旗舰"),
        ModelPricing(
            "qwen3.7-plus",
            "alibaba",
            "Qwen3.7 Plus",
            Decimal("0.40"),
            Decimal("1.60"),
            1000000,
            enabled=False,
            notes="官方为阶梯计费，长上下文输出价会更高；此处使用最低档运营价。",
        ),
        ModelPricing("qwen3.6-flash", "alibaba", "Qwen3.6 Flash", Decimal("0.25"), Decimal("1.50"), 1000000, enabled=False, notes="内部降本备选；默认产品清单只展示 Qwen3.7 Max。"),
        ModelPricing("qwen-plus", "alibaba", "Qwen Plus", Decimal("0.40"), Decimal("1.20"), 128000, enabled=False, notes="历史兼容模型；新会话建议优先选择 Qwen3.7 Max。"),
        ModelPricing("qwen-turbo", "alibaba", "Qwen Turbo", Decimal("0.05"), Decimal("0.20"), 1000000, enabled=False, notes="历史兼容模型；新会话建议优先选择 Qwen3.7 Max。"),
        ModelPricing(
            "doubao-seed-1-6",
            "volcengine",
            "Doubao Seed 1.6",
            Decimal("0.15"),
            Decimal("0.60"),
            256000,
            enabled=False,
            notes="火山方舟生产环境通常使用自建 endpoint ID；可用 custom 模型覆盖。",
        ),
        ModelPricing("doubao-seed-1-6-thinking", "volcengine", "Doubao Seed 1.6 Thinking", Decimal("0.60"), Decimal("2.40"), 256000, enabled=False, notes="国内供应商备选，可通过后台配置打开。"),
        ModelPricing("kimi-k2.7-code", "moonshot", "Kimi K2.7 Code", Decimal("1.00"), Decimal("4.00"), 128000, category="代码与 Agent"),
        ModelPricing("kimi-k2", "moonshot", "Kimi K2", Decimal("0.60"), Decimal("2.50"), 128000, enabled=False, notes="历史兼容模型；新会话建议优先选择 Kimi K2.7 Code。"),
        ModelPricing("grok-4.3", "xai", "Grok 4.3", Decimal("1.25"), Decimal("2.50"), 1000000, enabled=False, notes="海外供应商备选，可通过后台配置打开。"),
        ModelPricing("grok-build-0.1", "xai", "Grok Build 0.1", Decimal("1.00"), Decimal("2.00"), 256000, enabled=False, notes="代码供应商备选；默认产品清单只展示 Kimi K2.7 Code。"),
        ModelPricing("grok-4.1", "xai", "Grok 4.1", Decimal("3.00"), Decimal("15.00"), 256000, enabled=False, notes="旧模型，当前目录默认隐藏。"),
        ModelPricing("grok-4", "xai", "Grok 4", Decimal("3.00"), Decimal("15.00"), 256000, enabled=False, notes="旧模型，当前目录默认隐藏。"),
        ModelPricing("grok-code-fast-1", "xai", "Grok Code Fast 1", Decimal("0.20"), Decimal("1.50"), 256000, enabled=False, notes="已被 Grok Build 0.1 取代，当前目录默认隐藏。"),
        ModelPricing("grok-3-mini", "xai", "Grok 3 Mini", Decimal("0.30"), Decimal("0.50"), 128000, enabled=False, notes="历史兼容模型；当前目录默认隐藏。"),
    ]
    return {item.id: item for item in models}


def get_model_pricing(model_id: str, catalog: dict[str, ModelPricing] | None = None) -> ModelPricing:
    resolved = (model_id or DEFAULT_CHAT_MODEL).strip()
    model_catalog = catalog or default_model_catalog()
    if resolved in model_catalog:
        return model_catalog[resolved]
    return ModelPricing(
        id=resolved,
        provider="custom",
        display_name=resolved,
        input_usd_per_1m=Decimal("0.50"),
        output_usd_per_1m=Decimal("1.50"),
        notes="自定义模型默认价格，请在生产环境配置真实价格。",
    )


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    ascii_words = len(re.findall(r"[a-zA-Z0-9_@./:+-]+", text))
    symbols = len(re.findall(r"[^\s\u4e00-\u9fffa-zA-Z0-9_@./:+-]", text))
    # Chinese tokenization is often near 1 char/token; English averages about 4 chars/token.
    english_chars = len(re.sub(r"[\u4e00-\u9fff]", "", text))
    english_estimate = max(ascii_words, math.ceil(max(english_chars - symbols, 0) / 4))
    return max(1, chinese + english_estimate + math.ceil(symbols / 2))


def calculate_charge(
    model: ModelPricing,
    usage: TokenUsage,
    *,
    minimum_credits_micros: int = 1,
) -> int:
    input_cost = Decimal(usage.input_tokens) * model.input_credits_per_1m / Decimal(1_000_000)
    output_cost = Decimal(usage.output_tokens) * model.output_credits_per_1m / Decimal(1_000_000)
    total_micros = (input_cost + output_cost) * Decimal(MICROS_PER_CREDIT)
    rounded = int(total_micros.to_integral_value(rounding=ROUND_CEILING))
    if usage.total_tokens <= 0:
        return 0
    return max(minimum_credits_micros, rounded)


def credits_to_micros(value: Decimal | int | float | str) -> int:
    amount = Decimal(str(value))
    if amount < 0:
        raise ValueError("credits must be non-negative")
    return int((amount * Decimal(MICROS_PER_CREDIT)).to_integral_value(rounding=ROUND_CEILING))


def micros_to_credits(value: int) -> Decimal:
    return Decimal(value) / Decimal(MICROS_PER_CREDIT)
