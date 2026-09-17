from __future__ import annotations

from typing import Any


DIRECT_STUDY_KIND = "direct_study_material"


def ensure_direct_study_material(task_data: dict[str, Any], day_data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ensure a task has a first material that is direct study content, not instructions.

    The generated article is intentionally self-contained so the review page can be
    used as a study reader. Original docs/materials are kept after the generated
    study guide.
    """
    task = dict(task_data or {})
    day = dict(day_data or {})
    payload = dict(task.get("link_payload") or {})
    detail = dict(payload.get("detail") or {})
    existing_materials = _existing_materials(detail)
    generated = {
        "label": f"复习精讲｜{str(task.get('title') or '复习任务')[:34]}",
        "source_index": 0,
        "page_url": "/review-site/materials/0",
        "generated_kind": DIRECT_STUDY_KIND,
        "content": build_direct_study_content(task, day, existing_materials),
    }
    materials = [generated]
    for index, material in enumerate(existing_materials, start=1):
        item = dict(material)
        item["source_index"] = index
        item["page_url"] = f"/review-site/materials/{index}"
        materials.append(item)

    detail["materials"] = materials
    detail.setdefault("objective", _objective(task, day))
    detail["content"] = generated["content"]
    detail.setdefault("steps", _default_steps(task))
    detail.setdefault("questions", _default_questions(task))
    detail.setdefault("deliverables", _default_deliverables(task, day))
    payload["detail"] = detail
    task["link_payload"] = payload
    task["docs"] = [
        {"label": str(item.get("label") or f"资料 {idx + 1}"), "source_index": idx, "page_url": f"/review-site/materials/{idx}"}
        for idx, item in enumerate(materials)
    ]
    if not task.get("reason"):
        task["reason"] = _objective(task, day)
    return task


def build_direct_study_content(task: dict[str, Any], day: dict[str, Any] | None = None, materials: list[dict[str, Any]] | None = None) -> str:
    day = day or {}
    materials = materials or []
    title = str(task.get("title") or "复习任务").strip() or "复习任务"
    tags = [str(tag) for tag in (task.get("tags") or []) if tag]
    reason = str(task.get("reason") or "").strip()
    day_label = str(day.get("day") or day.get("day_label") or "").strip()
    day_title = str(day.get("title") or "").strip()
    acceptance = str(day.get("acceptance") or "").strip()
    category = _category(title, tags)
    core = _category_core(category)
    topic = _topic_study_pack(title, day_title, tags)
    source_summary = _source_summary(materials)
    tag_text = "、".join(tags) or "综合能力"

    return f"""# {title}

> 所属计划：{day_label or "复习日"} · {day_title or "专项复习"}。这是一篇可直接阅读学习的复习正文。

## 本项要掌握什么

本项核心标签：{tag_text}。

你需要掌握的不只是定义，而是把「{title}」放到真实工程里理解：它解决什么问题、处在哪一层、怎么实现、有哪些风险、如何验证、面试时如何表达。

{f"任务背景：{reason}" if reason else "任务背景：围绕该主题建立可复述、可举例、可落地的知识体系。"}

{f"当天验收口径：{acceptance}" if acceptance else "验收口径：能独立讲清概念、原理、实现路径、风险和生产指标。"}

{core}

{topic["deep_dive"]}

## 多轮面试考察方式

{topic["interview_rounds"]}

## 生产项目中的落地方式

如果把「{title}」接入真实生产项目，不能只做成聊天窗口或提示词片段，而要放进一条可治理链路：用户提出目标，系统构造上下文，模型生成决策，运行时校验权限，工具在沙箱里执行，验证器检查结果，审计系统记录完整轨迹。

最小可落地版本可以从只读能力开始：读取项目文档、解释代码、总结方案、生成风险清单。第二阶段再进入建议模式：生成 patch、测试建议、接口草案，但必须人工确认。第三阶段才允许受控执行：在沙箱里运行测试、lint、构建和低风险脚本。所有高风险动作都需要审批、审计和回滚方案。

{topic["production"]}

### 推荐架构

- **客户端层**：Web/Desktop/CLI/IDE，用于输入目标、查看资料、确认权限、审查 diff。
- **控制面**：用户、租户、项目、权限、模型、预算、策略和审计。
- **Agent Runtime**：任务状态机、上下文构造、模型调用、工具调度、暂停恢复。
- **工具层**：文件读取、搜索、Patch、Shell、Git、CI、浏览器、内部 API、MCP。
- **知识层**：项目索引、RAG、源码摘要、文档库、历史任务轨迹。
- **安全层**：沙箱、审批、脱敏、prompt injection 防护、网络白名单。
- **评测层**：离线场景、轨迹回放、线上指标、人工抽检和失败样本库。

## 工程实现要点

### 输入、处理、输出

- **输入**：用户目标、项目规则、历史事件、检索结果、可用工具、权限策略、预算限制。
- **处理**：构造上下文、调用模型、解析结构化输出、校验工具参数、执行工具、回填观察、循环迭代。
- **输出**：最终回答、patch、测试结果、风险说明、审计事件、可复用记忆、评测样本。

### 数据结构

```ts
type AgentTask = {{
  id: string;
  projectId: string;
  goal: string;
  status: 'planning' | 'running' | 'waiting_approval' | 'verifying' | 'done' | 'failed';
  budget: {{ maxTokens: number; maxToolCalls: number; maxCostUsd: number }};
}};

type AgentEvent =
  | {{ type: 'user_message'; text: string; at: string }}
  | {{ type: 'model_decision'; summary: string; toolCall?: unknown; at: string }}
  | {{ type: 'tool_result'; tool: string; success: boolean; summary: string; at: string }}
  | {{ type: 'approval'; approved: boolean; reason: string; at: string }}
  | {{ type: 'verification'; command: string; passed: boolean; at: string }};
```

### 参考流程

```ts
async function runAgentTask(task: AgentTask) {{
  const context = await buildContext(task);
  while (!isTerminal(task.status)) {{
    const decision = await callModel(context);
    await appendEvent(task.id, {{ type: 'model_decision', summary: decision.summary, at: now() }});
    if (decision.toolCall) {{
      const risk = classifyToolRisk(decision.toolCall);
      if (risk.requiresApproval) return waitForApproval(task, decision.toolCall);
      const observation = await executeToolInSandbox(decision.toolCall);
      context.addObservation(observation);
    }} else {{
      return verifyAndFinish(task, decision.finalAnswer);
    }}
  }}
}}
```

## 关键风险与常见坑

- 把模型当执行器：模型只生成决策，真实执行必须由 Runtime 和工具层控制。
- 忽略权限：能调用工具不代表应该调用工具，高风险动作必须审批。
- 上下文缺事实：模型会根据假设回答，必须通过检索、读文件、测试来查证。
- 只看最终答案：Agent 质量还取决于过程、验证、安全和成本。
- 没有评测集：没有回放评测，就无法判断 prompt、模型或工具改动是否退化。
- 没有审计：出了问题后无法回答模型看过什么、做过什么、谁批准过什么。

## 生产指标

- **任务成功率**：最终是否满足验收条件。
- **工具成功率**：工具调用参数正确、执行成功、输出可用的比例。
- **人工采纳率**：用户接受回答、patch 或建议的比例。
- **回滚率**：Agent 变更被撤销或引发回归的比例。
- **平均成本**：每个任务的 token、工具资源和运行时间。
- **安全事件数**：越权尝试、敏感信息暴露、危险命令拦截次数。

## 原资料要点

{source_summary}

## 面试可直接使用的回答

{topic["answer"]}

## 速记版

{topic["cheatsheet"]}
"""


def _existing_materials(detail: dict[str, Any]) -> list[dict[str, Any]]:
    materials = detail.get("materials") if isinstance(detail, dict) else []
    result: list[dict[str, Any]] = []
    if not isinstance(materials, list):
        return result
    for item in materials:
        if not isinstance(item, dict):
            continue
        if str(item.get("generated_kind") or "").startswith(DIRECT_STUDY_KIND):
            continue
        if str(item.get("label") or "").startswith("复习精讲"):
            continue
        result.append(dict(item))
    return result


def _category(title: str, tags: list[str]) -> str:
    text = " ".join([title, *tags]).lower()
    if any(key in text for key in ("llm", "大模型", "token", "transformer", "human")):
        return "llm"
    if any(key in text for key in ("tool", "mcp", "schema", "工具")):
        return "tool"
    if any(key in text for key in ("rag", "检索", "memory", "记忆", "知识")):
        return "rag"
    if any(key in text for key in ("codex", "claude", "源码", "code")):
        return "coding_agent"
    if any(key in text for key in ("安全", "sandbox", "权限", "prompt injection")):
        return "security"
    if any(key in text for key in ("评测", "eval", "指标", "观测")):
        return "eval"
    return "general"


def _category_core(category: str) -> str:
    cores = {
        "llm": """## 核心知识正文

大模型可以理解为条件概率模型：给定上下文 token 序列，预测下一个 token 的概率分布。Transformer 通过 self-attention 让每个 token 根据上下文重新计算表示。对 AI Agent 来说，LLM 不是执行器，而是决策器：它读取系统规则、用户目标、项目上下文、工具说明和工具结果，然后生成下一步动作或最终答案。

token 是成本、延迟和能力边界的共同单位。Agent 上下文通常包含系统规则、项目规则、用户目标、历史轨迹、相关文件、工具结果、错误日志和输出格式。上下文太长会增加成本并稀释注意力，太短会缺少事实依据。生产系统通常把规则常驻、事实检索、轨迹摘要、错误压缩分开处理。
""",
        "tool": """## 核心知识正文

Tool Calling 是 AI Agent 从“会说”变成“会做”的分界线。没有工具时，模型只能生成文本；有工具后，模型可以请求读取文件、搜索代码、调用 API、运行测试、生成 patch。关键点是：模型只产生调用意图，真正执行由 Agent Runtime 控制。

一个工具至少包含工具名、用途描述、输入 schema、输出 schema、风险等级、超时和幂等性。输入 schema 用来约束参数，输出 schema 用来让模型理解执行结果。生产系统不能相信模型自己声明的风险等级，必须由策略引擎重新计算。
""",
        "rag": """## 核心知识正文

RAG 解决的是模型不知道当前项目事实的问题。模型参数里没有你的私有代码、最新文档、团队规范和历史故障，所以需要检索把相关证据放进上下文。RAG 流程包括切分、索引、召回、重排、上下文拼接和引用追溯。

代码库 RAG 和普通文档 RAG 不同。代码有符号、路径、调用关系、测试关系和配置语义。生产系统通常组合关键词检索、向量检索、符号索引和最近编辑文件，而不是只依赖一种检索方式。
""",
        "coding_agent": """## 核心知识正文

Coding Agent 的核心价值是把“理解代码、修改代码、验证结果”串成闭环。它不是只生成代码片段，而是能读取项目、制定计划、编辑文件、运行命令、根据错误修复，并最终给出变更摘要和风险说明。

Claude Code 和 Codex 都可以作为架构学习对象。Claude Code 更适合学习终端/IDE 工作流、MCP 生态和项目上下文；Codex 更适合学习开源 CLI、沙箱、patch、项目规则和任务隔离。生产接入时应抽取共同架构，而不是照搬某个产品。
""",
        "security": """## 核心知识正文

Agent 安全的核心威胁是模型会把不可信文本当成指令，并且它有工具能力。恶意 README、网页、issue、日志都可能诱导模型忽略规则、读取密钥或执行危险命令。防护原则是：外部内容永远是数据，不是指令。

安全需要分层：提示词防护、上下文隔离、工具权限、沙箱执行、输出脱敏、审计日志、评测红队和人工审批。每层都可能失败，所以要做纵深防御。
""",
        "eval": """## 核心知识正文

Agent 评测不能只看最终答案是否像对的。结果质量、过程质量和安全质量都要评估。结果质量看任务是否完成，过程质量看是否读了必要文件并根据错误修复，安全质量看是否越权、泄露信息或跳过审批。

真实评测集应来自生产任务：代码理解、bug 修复、测试补全、文档生成、依赖升级、CI 失败诊断。每个场景都需要固定输入、允许工具、期望结果、评分 rubric 和安全约束。
""",
        "general": """## 核心知识正文

AI Agent 开发可以抽象为六个问题：模型如何决策，工具如何执行，状态如何保存，知识如何进入上下文，风险如何控制，结果如何验证。每个复习主题都要回到这六个问题里理解。

一个可用 Agent 和一个 demo 的区别在于失败处理。demo 展示成功路径，生产 Agent 必须处理上下文不足、工具失败、权限拒绝、输出格式错误、测试失败、成本超限和用户中途改目标。
""",
    }
    return cores.get(category, cores["general"])


def _topic_study_pack(title: str, day_title: str, tags: list[str]) -> dict[str, str]:
    text = " ".join([title, day_title, *tags]).lower()
    for keys, pack in _AGENT_TOPIC_PACKS:
        if any(key in text for key in keys):
            return pack
    return _DEFAULT_AGENT_TOPIC_PACK


_DEFAULT_AGENT_TOPIC_PACK = {
    "deep_dive": """## 岗位专项精讲

Agent 开发岗位考察的不是“会不会调一个模型接口”，而是能不能把大模型能力变成稳定、可控、可评估的软件系统。回答任何主题时都要落到四个层面：意图理解、上下文构造、工具执行、结果验证。模型负责生成候选动作，Runtime 负责约束动作，工具负责访问真实世界，评测负责证明系统没有退化。

一个成熟 Agent 通常包含计划器、执行器、记忆、工具注册中心、策略引擎、观测系统和评测系统。计划器把目标拆成阶段；执行器维护状态并调用模型；记忆保存可复用事实；工具注册中心描述能力和风险；策略引擎决定哪些动作可自动执行；观测系统记录轨迹；评测系统把历史任务回放成质量门禁。""",
    "interview_rounds": """- **一面技术面**：会问 Agent 和普通 LLM 应用的区别、工具调用如何建模、状态机如何设计、失败如何重试。
- **二面项目深挖**：会追问你做过的系统中数据从哪里来、权限怎么控、指标怎么证明有效、线上失败怎么定位。
- **三面系统设计**：会给一个业务场景，让你设计从前端入口、后端编排、模型调用、工具执行到评测上线的完整链路。
- **交叉面/主管面**：会关注取舍，尤其是成本、可靠性、灰度、团队协作、产品价值和风险边界。""",
    "production": """生产接入时优先把 Agent 做成“受控自动化平台”，而不是单点智能功能。所有工具都要有 schema、权限、超时、重试、审计和风险等级；所有模型输出都要能被解析、校验、拒绝或降级；所有关键任务都要能回放和复盘。""",
    "answer": "我会把这个问题放到 Agent 系统架构里回答：模型负责根据上下文生成决策，Runtime 负责状态机、预算和恢复，工具层负责受控执行，安全层负责权限和沙箱，评测层负责证明结果可靠。真实生产接入不会一步到位全自动，而是从只读问答开始，逐步到建议 patch、受控执行和低风险自动化。这样既能体现效率，也能保证可控、可审计、可回滚。",
    "cheatsheet": """- 定义：Agent 是由模型决策、工具执行、状态管理和结果验证组成的受控系统。
- 原理：模型生成下一步，Runtime 校验并执行，Observation 回填上下文形成闭环。
- 工程：工具 schema、权限、沙箱、审计、幂等、超时和重试是生产底线。
- 生产：从只读到建议再到受控执行，逐步灰度，持续评测。
- 面试：回答必须包含架构位置、失败模式、指标和项目落地。""",
}


_AGENT_TOPIC_PACKS: list[tuple[tuple[str, ...], dict[str, str]]] = [
    (("自我介绍", "岗位定位", "简历主线", "项目索引"), {
        "deep_dive": """## 岗位专项精讲

Agent 开发岗位的自我介绍要把你定位成“能把大模型能力工程化落地的人”。结构可以是：一句定位、两条主线、三个证据。定位不要泛泛说“熟悉 AI”，而要说清你能负责从需求分析、Agent 架构、工具链路、前后端交付、评测上线到生产运维的闭环。

项目索引建议准备三类案例。第一类是 Agent/RAG/AI Native 项目，用来证明你理解模型、检索、工具、评测和安全。第二类是复杂前端/跨端/桌面项目，用来证明你能做工程化和用户体验。第三类是生产稳定性案例，用来证明你能处理 SLA、灰度、回滚、监控和故障复盘。每个案例都要准备“背景、本人职责、关键设计、指标、失败处理、复盘”六要素。""",
        "interview_rounds": """- **HR/主管面**：重点判断你的岗位匹配度、动机和项目真实性。
- **技术一面**：会从你自我介绍里的 Agent/RAG 项目切入，验证你是否真的做过架构和落地。
- **技术二面**：会挑一个指标或故障追问口径，例如成功率怎么统计、召回怎么评估、工具失败怎么恢复。
- **终面**：会看你能否把个人经历映射到团队当前业务，而不是只讲技术名词。""",
        "production": """自我介绍里的生产项目不要只讲功能，要讲完整交付路径：需求从哪个业务痛点来，为什么需要 Agent，数据和权限如何接入，如何灰度给内部用户，如何观测 token 成本和任务成功率，出现误操作或低质量回答时如何降级和回滚。""",
        "answer": "我会把自己定位成 AI Native/Agent 工程方向的全栈候选人，优势不是只会写 prompt，而是能把模型、RAG、工具调用、权限、评测、前端体验和生产稳定性串成闭环。过往项目我会重点展开 Agent/RAG 落地、跨端或桌面工程化、线上质量治理三条证据，并明确本人负责的设计、指标和复盘。",
        "cheatsheet": """- 定位：AI Agent 工程化交付，不是单纯模型调用。
- 主线：Agent/RAG 能力、跨端工程、生产稳定性。
- 证据：本人职责、关键设计、量化指标、故障复盘。
- 避坑：不虚构指标，不把团队成果全部说成个人成果。
- 追问：为什么这样设计、失败怎么处理、如何证明有效。""",
    }),
    (("react", "reason", "act", "agent / rag / mcp", "工具调用", "mcp", "tool"), {
        "deep_dive": """## 岗位专项精讲

Agent 的基本循环可以理解为 Reason、Act、Observe：模型先基于目标和上下文推理下一步，再选择工具行动，工具结果作为 Observation 回到上下文。面试时不要把 ReAct 讲成固定 prompt 模板，而要讲成一种控制流：每一步都可能产生工具调用、等待审批、失败重试或终止。

Tool Calling 的关键是 schema 和边界。schema 限定模型能传什么参数，运行时决定这个工具是否允许执行，执行器负责超时、重试、幂等和错误归一化。MCP 可以理解为工具和上下文的协议层，让不同数据源、IDE、浏览器、文件系统、CI 或内部服务用统一方式接入 Agent。面试高分点是说清：工具说明影响模型选择，权限策略决定能否执行，Observation 质量影响下一轮推理。""",
        "interview_rounds": """- **基础追问**：Agent 和 Function Calling 有什么关系？工具 schema 为什么重要？
- **工程追问**：工具失败、超时、重复提交、参数不合法时怎么处理？
- **安全追问**：模型想调用删除文件或转账工具时，系统如何拦截？
- **系统设计追问**：给一个企业知识助手，如何用 MCP 接内部文档、代码库和工单系统？""",
        "production": """生产项目中要为每个工具维护元数据：用途、输入 JSON Schema、输出摘要策略、风险等级、是否幂等、超时、重试次数、权限 scope、审计字段和降级方案。只读工具可以默认开放；写操作、外部提交、付费调用、数据导出必须审批；不可逆动作必须拆成预览和确认两步。""",
        "answer": "我会把 Agent 工具调用设计成模型决策和运行时执行的分离：模型只输出结构化 tool call，后端根据 schema、权限、风险等级和预算校验，再在受控环境执行。MCP 或类似协议负责把外部能力标准化接入，但真正的安全边界在服务端策略、沙箱、审计和人工确认。",
        "cheatsheet": """- ReAct：Reason -> Act -> Observe 的控制循环。
- Tool：schema 约束输入，Runtime 决定执行，Observation 回填事实。
- MCP：统一暴露工具和上下文，不等于放开权限。
- 风险：参数错、超时、重复提交、越权、prompt injection。
- 高分回答：工具元数据 + 策略引擎 + 审计 + 降级。""",
    }),
    (("rag", "检索", "知识库", "召回", "embedding"), {
        "deep_dive": """## 岗位专项精讲

RAG 是 Agent 获取私有事实的主要方式。它不是“向量库一查就完”，而是一条证据链：文档接入、清洗切分、元数据建模、索引、召回、重排、上下文拼接、引用展示和反馈迭代。Agent 场景下 RAG 还要服务于行动，例如找相关代码、定位接口、读取规范、解释错误日志。

代码和业务文档的 RAG 策略不同。业务文档适合按标题、段落、版本和权限切分；代码更需要路径、符号、依赖、测试和最近修改记录。高质量 RAG 要组合关键词检索、向量召回、符号索引、重排模型和规则过滤。面试时要明确：RAG 的目标不是塞更多上下文，而是给模型提供最少但足够的证据。""",
        "interview_rounds": """- **算法/基础面**：embedding、chunk、top-k、rerank、召回率和精确率。
- **项目面**：你的知识库如何更新？权限怎么做？引用怎么展示？
- **Agent 面**：工具结果和检索结果冲突时如何处理？代码库如何检索？
- **生产面**：如何评估 RAG 有没有提升，如何定位幻觉来自召回还是生成？""",
        "production": """生产接入要把 RAG 做成可观测链路。每次回答都保存 query、召回文档、重排分、被引用片段、模型输入摘要和用户反馈。权限必须前置过滤，不能先召回再让模型“不要看”。质量指标包括 answer groundedness、引用命中率、无答案拒答率、人工采纳率和失败样本分布。""",
        "answer": "我会把 RAG 设计成证据链而不是单个向量库：先按数据类型和权限做接入与切分，再组合关键词、向量和符号检索，经过重排后把少量高置信证据交给模型，并在回答中保留引用和可回放轨迹。线上通过召回质量、引用命中、拒答率和人工反馈来闭环优化。",
        "cheatsheet": """- RAG：把私有事实以证据方式送进上下文。
- 流程：接入 -> 切分 -> 索引 -> 召回 -> 重排 -> 拼接 -> 引用。
- 代码库：路径、符号、调用关系、测试关系比纯语义更重要。
- 权限：检索前过滤，避免越权片段进入上下文。
- 评估：召回、groundedness、引用、拒答和反馈。""",
    }),
    (("memory", "记忆", "上下文", "context", "token"), {
        "deep_dive": """## 岗位专项精讲

Agent 记忆分三类：短期上下文、任务轨迹记忆和长期用户/项目记忆。短期上下文支撑当前轮推理；轨迹记忆记录做过什么、工具返回什么、为什么失败；长期记忆保存稳定偏好、项目规则和可复用事实。面试要强调记忆不是越多越好，必须有写入条件、过期策略、权限隔离和可删除能力。

上下文工程的核心是压缩和分层。系统规则、项目规则、用户目标、检索证据、工具结果、错误摘要、历史决策不能混在一起无序堆叠。一个好的 Runtime 会根据任务阶段选择上下文：计划阶段需要目标和约束，编辑阶段需要相关文件和规范，验证阶段需要测试结果和错误日志。""",
        "interview_rounds": """- **基础追问**：短期记忆和长期记忆区别是什么？
- **工程追问**：token 超限怎么办？历史轨迹如何摘要不会丢关键事实？
- **隐私追问**：用户记忆如何删除？租户之间如何隔离？
- **系统设计追问**：多轮 Agent 任务中断后如何恢复？""",
        "production": """生产中建议把记忆写入做成显式事件：来源、作用域、置信度、过期时间、敏感等级和用户可见性都要保存。摘要必须保留决策、文件、错误、审批和未完成事项。对敏感内容默认不进入长期记忆，跨项目和跨租户绝不复用。""",
        "answer": "我会把 Agent 记忆拆成短期上下文、任务轨迹和长期记忆。短期上下文用于当前推理，轨迹用于恢复和审计，长期记忆只保存稳定且被允许复用的事实。工程上通过作用域、TTL、敏感等级、用户可删除和摘要回放来控制质量与隐私。",
        "cheatsheet": """- 三类记忆：短期上下文、任务轨迹、长期记忆。
- 上下文：按阶段选择事实，不做无序堆叠。
- 摘要：保留决策、工具结果、错误、审批和待办。
- 隔离：用户、租户、项目作用域必须明确。
- 风险：污染、过期、泄露、token 浪费。""",
    }),
    (("评测", "eval", "指标", "质量", "benchmark"), {
        "deep_dive": """## 岗位专项精讲

Agent 评测要同时评估结果、过程和安全。结果看任务是否完成；过程看是否读了必要资料、调用了合理工具、根据错误迭代；安全看是否越权、泄密、执行危险动作或被 prompt injection 诱导。只用人工主观评分不够，只看自动指标也不够，生产上通常是离线回放、规则检查、LLM-as-Judge 和人工抽检组合。

评测集应来自真实任务，而不是凭空编题。比如代码理解、bug 修复、单测补全、CI 失败诊断、RAG 问答、工具调用、权限拒绝、恶意文档注入。每个 case 要固定输入、允许工具、期望产物、评分 rubric、禁用动作和通过阈值。这样模型、prompt、工具或检索策略变化时才能比较是否退化。""",
        "interview_rounds": """- **基础追问**：Agent 评测和普通问答评测有什么区别？
- **项目追问**：你们如何构造 eval set，如何避免只测 happy path？
- **上线追问**：模型升级如何做质量门禁？线上失败如何回流成样本？
- **管理追问**：质量、成本、延迟和安全指标冲突时怎么取舍？""",
        "production": """生产评测闭环包括五步：线上任务采样、失败归因、标注成 eval case、离线回放比较、通过门禁后灰度发布。关键指标是任务成功率、人工采纳率、工具调用准确率、一次通过率、平均迭代轮数、成本、延迟、安全拦截率和回滚率。""",
        "answer": "我会把 Agent 评测分成结果、过程和安全三层。结果层看产物是否满足验收，过程层看工具和推理轨迹是否合理，安全层看是否越权或泄露。落地时用真实任务构建回放集，结合规则检查、LLM-as-Judge 和人工抽检，并把线上失败持续回流到 eval set。",
        "cheatsheet": """- 三层：结果质量、过程质量、安全质量。
- 样本：来自真实线上任务和失败案例。
- 方法：规则、回放、LLM Judge、人工抽检组合。
- 指标：成功率、采纳率、工具准确率、成本、延迟、安全事件。
- 上线：模型/prompt/工具改动必须过质量门禁。""",
    }),
    (("安全", "沙箱", "权限", "prompt injection", "越权"), {
        "deep_dive": """## 岗位专项精讲

Agent 安全比普通 LLM 应用更关键，因为 Agent 有工具能力。攻击面包括恶意文档、网页、仓库文件、issue、日志、工具输出和用户输入。核心原则是：外部内容永远是数据，不是指令；模型输出永远是建议，不是授权；执行权限永远由服务端策略决定。

沙箱要限制文件系统、网络、环境变量、进程、执行时间和资源。权限要按用户、租户、项目、工具和动作细分。危险动作要拆成 dry-run、diff 预览、人工确认和可回滚提交。敏感信息要在进入模型前脱敏，工具输出也要做最小化摘要，避免把密钥、token 或个人隐私带进上下文。""",
        "interview_rounds": """- **安全面**：prompt injection 如何防？恶意 README 要求读取密钥怎么办？
- **工程面**：沙箱如何设计，哪些命令要禁止，网络如何控制？
- **系统面**：多租户下权限、审计和数据隔离怎么做？
- **事故复盘**：如果 Agent 执行了错误操作，如何定位、止血、回滚和补评测？""",
        "production": """生产安全要做纵深防御：输入分层、指令/数据隔离、工具 allowlist、参数校验、风险分类、人工审批、沙箱执行、输出脱敏、审计回放和红队评测。不要依赖提示词承诺安全，真正的边界必须在代码和基础设施里。""",
        "answer": "我会把 Agent 安全设计成纵深防御：不可信内容只当数据，模型输出只当建议，工具执行由服务端策略和沙箱控制。高风险动作必须审批和可回滚，敏感数据进入模型前脱敏，所有工具调用都记录审计轨迹，并用 prompt injection 和越权样本做持续评测。",
        "cheatsheet": """- 原则：外部内容是数据，模型输出是建议，服务端策略才是授权。
- 沙箱：限制文件、网络、环境变量、进程、时间和资源。
- 权限：用户、租户、项目、工具、动作五层隔离。
- 审批：危险动作 dry-run、预览、确认、回滚。
- 评测：prompt injection、越权、泄密、危险命令。""",
    }),
    (("claude", "codex", "源码", "code agent", "coding agent"), {
        "deep_dive": """## 岗位专项精讲

学习 Claude Code 和 Codex 的重点不是背产品功能，而是抽取 Coding Agent 的通用架构。Codex 开源 CLI 适合重点看项目规则加载、工具执行、patch 编辑、沙箱策略、Git 工作流、任务上下文和终端交互。Claude Code 适合结合官方文档和公开仓库学习终端体验、MCP 接入、项目记忆、权限确认和长任务协作。注意 Claude Code 的商业产品内部源码不能假设可见；面试中应强调只基于官方文档、公开仓库和可观察行为分析。

源码阅读可以按链路拆：入口命令如何解析，项目上下文如何初始化，AGENTS/规则文件如何进入上下文，模型调用如何封装，工具如何注册和执行，patch 如何生成和校验，shell 命令如何进入沙箱，错误如何回填，最终回答如何汇总。读源码时不要陷入细枝末节，先画模块图和一次任务的时序图。""",
        "interview_rounds": """- **源码面**：让你解释一个 Coding Agent 从收到需求到提交 patch 的完整调用链。
- **架构面**：问 Claude Code/Codex 这类工具为什么需要项目规则、沙箱、审批和 Git 隔离。
- **工程面**：问如何实现文件编辑、命令执行、终端输出摘要、失败重试和上下文压缩。
- **产品面**：问 CLI、IDE、Web、桌面形态各自适合什么用户流。""",
        "production": """生产项目接入 Coding Agent 时，不建议一开始让它直接改主仓库。更稳的方式是独立任务、隔离 worktree、受控 shell、diff 审查、测试门禁、PR 提交和审计记录。企业场景还要接权限系统、代码库权限、密钥管理、依赖安全扫描和成本限额。""",
        "answer": "我会从 Coding Agent 的通用链路来学习 Claude Code 和 Codex：入口命令、项目上下文、规则加载、模型调用、工具注册、沙箱执行、patch 生成、Git 隔离和验证反馈。Codex 可以重点看开源 CLI 和沙箱实现，Claude Code 则基于官方文档和公开能力分析 MCP、权限和终端工作流；生产落地要用 worktree、审批、测试门禁和审计保证可控。",
        "cheatsheet": """- 读源码链路：CLI -> context -> model -> tool -> sandbox -> patch -> test -> summary。
- Codex：重点看开源 CLI、规则、patch、沙箱、Git 工作流。
- Claude Code：重点看官方能力、MCP、权限、项目记忆和终端体验。
- 边界：不假设不可见商业源码，基于公开资料分析。
- 生产：worktree 隔离、diff 审查、测试门禁、PR 和审计。""",
    }),
    (("系统设计", "全链路", "工作台", "平台", "生产闭环"), {
        "deep_dive": """## 岗位专项精讲

Agent 系统设计题常见场景包括：企业知识助手、代码修复 Agent、面试复习 Agent、投研助手、客服工单 Agent、数据分析 Agent。答题框架固定但要能落地：先定义用户和目标，再定义任务边界，然后画出客户端、API、Agent Runtime、模型网关、工具服务、知识库、评测系统、审计系统和运维面板。

系统设计的高分点是边界意识。哪些任务自动完成，哪些只给建议，哪些必须人工确认？哪些数据可以进模型，哪些需要脱敏，哪些要本地执行？如何做租户隔离、成本预算、限流、排队、取消、恢复和重试？如何证明上线后有业务价值？这些问题比多堆几个模型名更重要。""",
        "interview_rounds": """- **系统设计面**：从 0 到 1 设计一个 Agent 平台，要求画模块和数据流。
- **追问一**：如何支持长任务、暂停恢复、用户审批和并发执行？
- **追问二**：如何做 RAG、工具调用、安全、评测和观测？
- **追问三**：如何从 MVP 灰度到商业化交付？""",
        "production": """商业化交付要补齐租户、套餐、配额、审计、权限、配置中心、模型策略、数据导入、知识库版本、任务队列、失败告警和客户可见报表。MVP 可以先做单租户和只读能力，但架构上要保留多租户隔离和审计字段。""",
        "answer": "我会先明确业务场景和自动化边界，再设计客户端、API、Agent Runtime、模型网关、工具服务、知识库、评测和审计。长任务用状态机和事件流保存轨迹，工具执行走权限和沙箱，RAG 走权限前置过滤，质量通过离线回放和线上指标闭环。商业化交付还要有租户、配额、套餐、审计和运维面板。",
        "cheatsheet": """- 架构：Client/API/Runtime/Model Gateway/Tools/RAG/Eval/Audit/Ops。
- 边界：只读、建议、受控执行、人工审批。
- 长任务：状态机、事件流、暂停恢复、取消重试。
- 商业化：租户、套餐、配额、审计、报表、SLA。
- 高分：讲清数据流、权限流、失败流和指标流。""",
    }),
]


def _source_summary(materials: list[dict[str, Any]]) -> str:
    if not materials:
        return "- 暂无额外原始资料；本篇精讲已经覆盖核心复习内容。"
    lines = []
    for index, item in enumerate(materials[:6], start=1):
        label = str(item.get("label") or f"资料 {index}")
        content = str(item.get("content") or "").strip().replace("\n", " ")
        if len(content) > 120:
            content = content[:120] + "..."
        lines.append(f"- 《{label}》：{content or '作为延伸阅读，重点对照本篇正文查漏补缺。'}")
    return "\n".join(lines)


def _objective(task: dict[str, Any], day: dict[str, Any]) -> str:
    title = str(task.get("title") or "复习任务")
    return f"掌握「{title}」的概念、原理、工程实现、风险和生产项目落地方式。"


def _default_steps(task: dict[str, Any]) -> list[str]:
    return ["阅读复习精讲正文。", "理解核心原理和工程实现。", "结合生产项目接入方式复述一遍。", "用面试回答模板压缩成 60 秒表达。"]


def _default_questions(task: dict[str, Any]) -> list[str]:
    title = str(task.get("title") or "这个主题")
    return [f"{title} 解决什么问题？", "它处在 Agent 架构的哪一层？", "生产项目接入时最大的风险是什么？", "如何验证它真的有效？"]


def _default_deliverables(task: dict[str, Any], day: dict[str, Any]) -> list[str]:
    return ["完成 5 行速记。", "能讲清一条工程链路。", "能说出生产指标、风险和回滚方式。"]
