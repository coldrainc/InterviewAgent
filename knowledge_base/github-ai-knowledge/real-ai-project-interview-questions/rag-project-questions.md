# RAG 项目真实面试题

## Q1: 你做过的 RAG 系统是如何从 0 到 1 设计的？

### 真实问法

“你简历里写做过企业知识库问答。请不要只讲 RAG 概念，按真实项目讲一下：业务目标是什么、数据从哪来、怎么切分、怎么检索、怎么评测、怎么上线？”

### 面试官想听什么

- 业务场景：客服、内部知识库、代码问答、投研、法务、售后、研发文档等。
- 数据链路：采集、解析、清洗、去重、权限、增量更新。
- 检索链路：query rewrite、BM25、向量召回、metadata filter、rerank、context packing。
- 生成链路：引用来源、拒答、置信度、结构化答案、流式输出。
- 评测指标：Recall@K、MRR、答案正确率、groundedness、幻觉率、用户满意度、人工采纳率。
- 线上指标：P50/P95 延迟、token 成本、缓存命中率、索引更新时间、错误率。

### 可继续追问

- 为什么选择这个 embedding 模型？有没有做过中英文、长文本、领域术语的对比？
- 如果召回到的文档是对的，但生成答案错了，你怎么定位？
- 如果生成答案对了，但引用来源错了，你怎么修？
- 权限过滤是在召回前、召回后，还是两者都做？为什么？
- 增量更新时怎么保证索引和原文一致？

### 高质量回答要点

一个扎实回答需要讲出完整闭环：原始文档先进入 ingestion pipeline，解析 PDF、HTML、Markdown、表格后统一成 Document schema；再按标题层级和语义边界 chunk，保留 parent document、section path、权限标签、时间戳等 metadata；在线查询时先做 query normalization 和 rewrite，再做 sparse+dense 多路召回，用 reranker 精排，最后按 token budget 做上下文压缩与拼装。上线前需要有 golden set 和人工标注集，持续评测召回、答案忠实度和端到端体验。

## Q2: RAG 召回率低，你具体怎么排查？

### 真实问法

“用户问的问题系统答不上来，你怎么判断是知识库没有、chunk 切坏了、embedding 不匹配，还是 rerank / prompt 的问题？”

### 面试官想听什么

- 先区分 failure mode：无文档、解析失败、分块失败、召回失败、排序失败、上下文被截断、生成失败。
- 建立 trace：query、召回候选、分数、metadata、rerank 前后、最终 prompt、模型输出。
- 做离线集：把失败 query 加入 eval cases，避免修一个坏一个。
- 用对照实验：chunk size、overlap、embedding 模型、top_k、reranker、query rewrite。

### 可继续追问

- 你怎么设计一个最小可用的 RAG eval dataset？
- query 很短，比如“报销”，你怎么召回准确？
- query 很长、包含多意图时怎么处理？
- 如果用户问题依赖历史对话，怎么做 conversational retrieval？

### 高质量回答要点

排查时不要直接调 prompt。先看知识库是否包含答案，再看解析后文本是否可检索，再看 chunk 是否保留标题与上下文，然后看 top_k 里是否召回目标 chunk。如果目标 chunk 在 top_k 但不在最终上下文，问题多半在 rerank 或 context packing；如果目标 chunk 完全没有召回，重点检查 embedding、BM25、query rewrite、metadata filter。最后才看生成 prompt 和拒答策略。

## Q3: 你如何设计企业级 RAG 的权限控制？

### 真实问法

“同一个知识库里有不同部门文档，用户只能看自己有权限的内容。你的 RAG 权限怎么做？只在答案返回前过滤可以吗？”

### 面试官想听什么

- 文档级、段落级、字段级 ACL。
- 索引 metadata 中保留 tenant_id、department、role、document_acl、version。
- 召回前过滤能减少泄漏风险；召回后过滤用于兜底。
- prompt 里不能暴露无权限内容；日志也要脱敏。
- 缓存必须带权限维度，避免 A 用户命中 B 用户答案。

### 可继续追问

- 多租户场景是每个租户一个 collection，还是共享 collection 加 metadata filter？
- 权限变更后如何让旧索引和缓存失效？
- reranker 和 LLM 请求是否会接触无权限内容？

### 高质量回答要点

生产级答案应该强调“权限前置”。最安全的设计是在检索阶段就带上用户身份和 ACL filter，候选文档只来自用户有权访问的范围；rerank 和生成只处理过滤后的 chunk。缓存 key 必须包含 tenant、role、权限版本和 query hash。权限变更时通过 ACL version 或 document version 触发索引与缓存失效。

## Q4: 为什么有时 RAG 会“看起来有引用但仍然幻觉”？

### 真实问法

“你的系统给了引用来源，但答案还是编的。你怎么解决这种 groundedness 问题？”

### 面试官想听什么

- 引用不等于答案被上下文支持。
- 需要 sentence-level attribution 或 answer span 校验。
- prompt 要要求“只基于上下文回答，不足则拒答”。
- 可引入 verifier / critic 模型检查答案是否被证据支持。
- 对高风险领域使用 extractive answer 或模板化输出。

### 可继续追问

- 怎么自动评估 groundedness？
- 什么时候应该拒答？
- 如果上下文相互矛盾怎么处理？

### 高质量回答要点

可靠方案是把答案生成拆成两步：先从上下文抽取可支持的证据点，再基于证据点生成答案；生成后再做校验，检查每个关键结论是否能映射到具体 chunk 或句子。若证据不足，系统应输出“不确定/需要更多信息”，而不是为了流畅性强答。

## Q5: RAG 项目如何做增量更新和自动更新？

### 真实问法

“知识库每天都有文档更新。你怎么做到自动更新？如何避免一边更新一边线上查到半旧半新的数据？”

### 面试官想听什么

- 数据源监听：Git webhook、对象存储事件、数据库 CDC、定时扫描。
- 文档 fingerprint：内容 hash、mtime、版本号。
- 增量索引：新增、更新、删除三类事件。
- 双写或影子索引：build new index，再原子切换 alias。
- 回滚策略：保留上一版本索引和构建日志。

### 可继续追问

- 删除文档时向量库里的旧向量怎么删除？
- 如何处理 PDF 解析失败？
- 如何保证 metadata 和 chunk 同步？

### 高质量回答要点

生产级方案一般不会直接在主索引上裸更新，而是使用版本化索引或 collection alias。构建流程先解析新文档，生成 chunk 和 embedding，写入新版本或 staging collection，校验 chunk count、抽样检索、权限 metadata 后再切换线上 alias。失败时继续使用旧版本，避免线上检索不一致。

## Q6: RAG 延迟太高，你怎么优化？

### 真实问法

“RAG 链路里 embedding、向量库、rerank、LLM 都耗时。你怎么把 P95 从 8 秒降到 2 秒以内？”

### 面试官想听什么

- 并行召回：BM25 和 vector 并发。
- query embedding 缓存、相似问题语义缓存。
- 降低 rerank 候选数，或小模型先粗排。
- context 控制，减少 LLM 输入 token。
- 流式输出改善感知延迟。
- 热点文档、热点 query 缓存。

### 可继续追问

- 你会优先优化哪一段？为什么？
- reranker 太慢怎么替代？
- 语义缓存会带来什么风险？

### 高质量回答要点

先用 trace 拆延迟，而不是盲调。通常召回可以并发，embedding 可以缓存，rerank 候选从 100 降到 20，最终上下文从 20 个 chunk 降到 5 个高质量 chunk。对高频问答可用 semantic cache，但 cache key 需要包含权限、知识库版本和模型版本。

## Q7: 你如何选择 chunk size 和 overlap？

### 真实问法

“你们 chunk_size 为什么设成 800，不是 512 或 2000？依据是什么？”

### 面试官想听什么

- chunk 大小取决于文档结构、问题粒度、embedding 模型长度、召回目标。
- 小 chunk 精确但缺上下文；大 chunk 召回粗且容易塞爆 prompt。
- overlap 解决边界问题，但会增加索引体积和重复召回。
- 用 eval set 做网格实验，而不是拍脑袋。

### 可继续追问

- 表格、代码、FAQ、长 PDF 的切分策略一样吗？
- parent-child retrieval 怎么解决小 chunk 缺上下文？
- 标题层级 metadata 有什么用？

### 高质量回答要点

合理回答应说“按文档类型分策略”。FAQ 可以一问一答为 chunk；技术文档按标题层级；代码文档按函数/类；表格要保留表头和行语义。线上一般会保留 child chunk 做精确召回，同时返回 parent section 做上下文补充。

## Q8: RAG 中 reranker 的价值是什么？什么时候不用？

### 真实问法

“你已经有向量检索了，为什么还要 rerank？reranker 会不会太慢？”

### 面试官想听什么

- 向量召回适合高召回，reranker 适合提高精排准确率。
- reranker 计算 query-document 交叉注意力，通常比 bi-encoder 更准但更慢。
- 候选数要控制，常见做法 top 50 召回后 rerank top 5。
- 低风险、低成本、低延迟场景可以不用。

### 可继续追问

- reranker 输入太长怎么办？
- rerank 分数怎么和 BM25 / vector 分数融合？
- reranker 失败时如何降级？

### 高质量回答要点

不要把 reranker 当银弹。它适合在召回候选质量还可以，但排序不稳定时使用。如果召回本身找不到答案，reranker 没法凭空修好。工程上要设超时和降级：reranker 超时则使用 hybrid score 排序，保证主链路可用。

