# AI 评测与质量体系要求

## 为什么评测是行业刚需

AI 功能不能只靠“人工试几个问题”。生产级项目需要可重复的质量准入机制，否则 prompt、模型、RAG、Agent 工具链每次变更都可能引入不可见回归。

## 评测层级

### 1. 单点能力评测

- 分类准确率。
- 信息抽取字段正确率。
- JSON schema 合规率。
- 摘要覆盖率。
- 翻译/改写质量。

### 2. RAG 评测

- Retrieval Recall@K。
- MRR / nDCG。
- Context Precision。
- Faithfulness / Groundedness。
- Answer Correctness。
- Citation Accuracy。
- Refusal Accuracy。

### 3. Agent 评测

- Task Success Rate。
- Tool Call Accuracy。
- Tool Parameter Accuracy。
- Step Count。
- Cost / Latency。
- Unsafe Action Rate。
- Recovery Rate。

### 4. 线上体验评测

- 用户采纳率。
- 点赞 / 点踩。
- 转人工率。
- 会话完成率。
- 重试率。
- 人工抽检通过率。

## 数据集设计

一个可用的 eval set 至少包含：

- 高频真实问题。
- 长尾问题。
- 边界问题。
- 无答案问题。
- 权限受限问题。
- Prompt injection 和安全攻击问题。
- 历史线上失败 case。
- 多轮对话问题。

## LLM-as-Judge 使用原则

LLM-as-Judge 可以降低人工成本，但不能无脑相信。

适合：

- 初筛大量样本。
- Pairwise preference。
- 风格、完整性、相关性判断。
- Groundedness 辅助判断。

不适合单独决定：

- 法律、医疗、金融等高风险结论。
- 权限和合规判定。
- 需要严格事实依据的最终准入。

应配套：

- judge prompt 版本化。
- judge 模型版本记录。
- 人工校准集。
- 与人工标注计算一致性。

## 质量门禁

上线前可设置门禁：

```text
schema_valid_rate >= 99%
retrieval_recall_at_5 >= 85%
groundedness >= 90%
unsafe_output_rate <= 0.5%
p95_latency <= 3s
cost_per_request <= budget
regression_cases_pass = 100%
```

不同业务门槛不同，但必须显式定义。

## 评测闭环

```text
线上 trace / 用户反馈
  -> 失败 case 分类
  -> 人工标注 / 自动 judge
  -> eval dataset
  -> prompt / retriever / model / tool 修复
  -> 回归评测
  -> 灰度上线
```

## 面试高频问题

### Q1: AI 项目上线前你怎么证明质量？

回答要点：离线 golden set、线上灰度、人工抽检、自动指标、失败回归集、风险分级。

### Q2: RAG 的答案正确率怎么评估？

回答要点：先评估 retrieval，再评估生成。检索看目标 chunk 是否召回，生成看答案是否正确、是否被上下文支持、引用是否准确。

### Q3: Agent 的评测为什么更难？

回答要点：Agent 不只是输出文本，还会改变环境。要评估轨迹、工具调用、参数、最终状态和副作用风险。

### Q4: 线上负反馈如何进入评测集？

回答要点：不能所有点踩直接进入训练。要分类、去重、脱敏、人工确认，形成高价值 regression cases。

