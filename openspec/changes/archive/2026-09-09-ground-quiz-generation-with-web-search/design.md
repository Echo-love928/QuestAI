## Context

现有 `POST /api/v1/quiz/generate` 由 `QuizService` 直接调用 `DeepSeekGateway`，`QUIZ_PROMPT` 只接收用户输入、题量、难度与 JSON Schema。`Quiz`、前端 `Quiz` 类型和 `quiz_sessions` 均没有资料来源字段；题库成功后会对登录用户做尽力保存，匿名流程不依赖数据库。首页虽然已有 URL 类型入口，但尚未接入正文获取流程。参见 [proposal.md](./proposal.md) 的范围与 [grounded-quiz-generation spec](./specs/grounded-quiz-generation/spec.md) 的行为契约。

当前后端锁定 `langchain-deepseek==0.1.4` 和 `langchain-core 0.3.x`。LangChain 1.x 以 `create_agent` 作为标准 Agent API，并支持模型连续、并行和动态选择工具；官方 Tavily 集成位于独立的 `langchain-tavily` 包，提供原生异步的 `TavilySearch` 与 `TavilyExtract`。实施前必须先锁定 `ChatDeepSeek` 工具调用、Agent 和现有结构化输出均通过兼容性测试的版本组合。

Tavily 当前提供国家级 `country` 排名增强而没有城市参数。因此城市范围不能映射为虚构字段，必须通过查询词表达城市/地区，再按需附加国家级增强。搜索的 `include_raw_content`、`max_results` 等参数并非都能在同一个 LangChain 工具实例上逐次动态修改，工具适配层需要把 Agent 的受控参数转换为本次调用的官方工具配置。

## Goals / Non-Goals

**Goals:**

- 同时支持关键词检索和公开网页 URL 正文提取，让 AI 根据任务和已有证据自主选择 `tavily_search`、`tavily_extract` 及调用顺序。
- 将 AI 自主研究限制在可测试的参数、次数、耗时和正文预算内，避免无限循环、费用失控和危险 URL。
- 对简单、复杂、时效、中文、国际和地域主题采用不同资料获取策略，同时保留跨语言第一方资料。
- 研究与最终出题分层；只有通过清洗和充分性校验的证据才能进入现有结构化题目生成流程。
- 保持匿名/登录、题型、答题、报告、XP 和历史流程兼容，新增 API 与数据库字段只增不删。

**Non-Goals:**

- 本次不实现 PDF、Word、音视频解析，也不建设长期 RAG 向量库。
- 本次不允许任意第三方工具、写操作工具或开放式浏览器操作；Agent 只能看到两个只读 Tavily 工具。
- 本次不允许 Agent 绕过服务层直接返回最终 API 题库，也不以网络来源存在作为“绝对正确”的承诺。
- 本次不改动报告算法、XP 规则、登录鉴权或用户资料功能。

## Decisions

### 1. 采用受控研究 Agent 与确定性出题的两阶段架构

完整链路为：

`输入分类/URL 安全校验 -> LangChain 研究 Agent -> Tavily Search/Extract -> 证据归一化与充分性评估 -> DeepSeek 结构化出题 -> 引用与题库校验`。

研究阶段使用 LangChain 1.x `create_agent` 和未预绑定工具的 `ChatDeepSeek` 实例，同时注册两个静态只读工具：`tavily_search` 与 `tavily_extract`。工具名称、描述和 Pydantic 参数 Schema 明确告诉模型适用场景；Agent 可直接搜索、直接提取用户 URL，或先搜索再提取重要结果，并在证据充分时停止调用。

Agent 最终输出结构化 `ResearchBrief`，包含解析后的主题、领域、歧义状态、证据关键事实及对应来源 ID。该输出必须经过服务层验证，随后再由现有独立 `DeepSeekGateway` 生成 `QuizDraft`。Agent 不直接产生公共题库，从而避免工具调用和最终 JSON Schema 相互干扰，并保留现有题量、题型和重试逻辑。

备选方案一是固定 Search/Extract 工作流，但无法满足 AI 根据结果自主追加提取的要求。备选方案二是让单个 Agent 直接研究并生成题库，链路更短，却更难分别验证证据充分性、来源引用和现有结构化输出，因此不采用。

### 2. 用受控适配器封装官方 TavilySearch 与 TavilyExtract

AI 看到的仍是 `tavily_search` 和 `tavily_extract` 两个工具。工具实现必须使用 `langchain-tavily` 官方类，不自行重新实现 Tavily HTTP 客户端：

- `tavily_search` 适配器接收查询、复杂度、结果数、主题、搜索深度、片段数、时间范围、国家和语言等受控参数；通过本次配置创建或选择 `TavilySearch` 实例，再执行原生异步调用。
- `tavily_extract` 适配器接收最多 3 个已校验 URL、可选相关查询、提取深度、每来源片段数和超时；内部调用 `TavilyExtract`，保留成功结果和 `failed_results`。
- 两个适配器统一映射返回值为内部证据候选，不向 Agent 暴露 API Key、上游异常栈或无限制参数。

之所以保留适配层，是因为 LangChain 集成中有些 Search 参数属于实例配置，不能仅依靠同一个工具实例的调用参数完成动态结果数量和正文策略。适配器让 Agent 仍只选择两个业务工具，同时确保所有动态参数可被 Pydantic 校验、测试和审计。

### 3. 复杂度决定摘要、结果数量和全文提取

系统 Prompt 提供决策原则，但所有数值由适配层强制收敛：

| 场景 | Search 深度 | 结果数 | 每来源片段 | Extract 策略 |
|---|---:|---:|---:|---|
| 简单、明确、稳定概念 | `fast` 或 `basic` | 3 | 1 | 摘要充分时不提取 |
| 新颖、专业、复杂或有歧义 | `advanced` | 5～8 | 2～3 | 提取最多 3 个高价值页面 |
| 最新版本、新闻或指定日期 | `advanced` | 5～8 | 2～3 | 设置匹配的 `topic`/`time_range`，必要时提取原文 |
| 用户直接提交 URL | 不默认搜索 | 0 | 0 | 先以 `basic` 提取；复杂页面可升级 `advanced` |

简单知识以搜索摘要作为证据，复杂知识采用“搜索发现来源 -> 提取正文”的组合，而不是让 Search 为所有结果返回完整原文。这样能减少上下文和费用，并让 Extract 只处理 Agent 选中的重要页面。

默认不启用 Tavily `auto_parameters`，因为它不会自动决定 `include_raw_content` 和 `max_results`，还可能自动选择更高成本的深度。Agent 显式选择语义参数，适配层执行确定性边界，更便于 TDD 和费用控制。

### 4. 中英文与地域策略采用查询增强而非严格过滤

研究 Agent 必须保留用户原词，并从输入推断首选语言。对于有通用英文原名的中文技术概念，查询可组合中文名、英文名和领域限定；不得把模型猜测的翻译替换掉用户原词。

- 全球技术主题：不设置 `country`，语言仅作为排序倾向，默认 `filter_by_language=false`。
- 国家相关主题：国家写入查询，并在 Tavily 支持时设置 `country` 排名增强。
- 城市/地区主题：城市或地区必须写入查询；能确定国家时再设置 `country`，因为 Tavily 没有城市参数。
- 用户明确要求限定资料语言时，才允许严格语言过滤；否则中文用户仍可获得英文官方文档，国际用户也能获得最相关的本地资料。

与固定中文检索相比，该设计更容易取得国际第一方资料；与不做语言增强相比，又能改善国内内容的召回和中文关键词歧义。

### 5. 后端硬限制 Agent 的调用与内容预算

Agent 自主性不等于无限权限。每次生成默认设置以下硬限制，均可通过有上限的配置调整：

- 网络工具调用总数最多 4 次。
- Search 最多 2 次，单次最多 8 条结果。
- Extract 全程最多处理 3 个唯一 URL，禁止通过多次调用绕过累计上限。
- 研究阶段设置独立总超时；单工具超时不得超过剩余预算。
- 证据来源最多 8 条，并设置单来源与总字符/Token 预算。
- 达到递归/迭代、时间或内容上限后停止工具调用，直接进行证据充分性评估。

LangChain Agent 本身以“模型结束或迭代限制”作为停止条件；应用层还必须累计工具调用、URL 和内容预算，不能只依赖 Prompt 自觉。工具错误通过 Agent middleware 转换为可处理的 `ToolMessage`，但连续失败或预算耗尽最终映射为稳定领域错误。

### 6. URL 校验和网页内容隔离在工具执行前完成

前端负责基础格式提示，后端负责最终安全判断。URL 必须满足：公开 HTTP(S)、无嵌入式用户名密码、主机名有效，且解析结果不是 localhost、环回、链路本地、私网、保留或云元数据地址。重定向后的目标也必须重新检查；同一规范化 URL 只计一次。

即使 Tavily 在外部抓取页面，系统也不应把内部或带凭据地址发送给第三方。网页正文、搜索摘要、页面标题及元数据全部视为不可信数据；Prompt 使用明确边界包裹，并声明其中的角色、命令、工具请求和输出格式要求均不得执行。

当用户 URL 提取失败时，Agent只可围绕该 URL 的域名、可获得的页面标题或用户主题进行受控补救搜索；补救结果必须标记为补充资料，不能冒充用户原页面。仍无法取得原文或足够证据时明确失败。

### 7. 证据归一化与充分性门槛独立于 Agent 判断

内部 `EvidenceSource` 至少包含 `source_id`、`title`、`url`、`site_name`、`content`、`acquisition_method`（`search_snippet`、`user_url_extract` 或 `search_result_extract`）、可选 `published_at`、相关度和获取时间。后端负责 URL 规范化、去重、内容裁剪和稳定来源 ID 分配。

`ResearchBrief` 的来源引用只能来自实际工具结果。服务层至少验证：主题和资料相关；存在一个高度相关的第一方来源，或至少两个不同站点相互支持；歧义已消解；关键事实均有关联来源。相关度分数不能单独证明事实正确。

公共 `QuizSource` 不返回完整抓取正文。题库增加 `grounding_mode`（`user_content`、`web_search`、`url_extract` 或 `mixed`）、`sources` 和可选 `researched_at`；每题增加 `source_ids`。最终出题模型只能引用提供的 `source_id`，服务层拒绝未知或空引用。

### 8. 失败类型可区分且不得静默使用模型记忆

新增领域错误类别：`ResearchUnavailable`、`SearchUnavailable`、`ExtractUnavailable`、`UnsafeUrl`、`EvidenceInsufficient`、`TopicAmbiguous` 和 `ResearchBudgetExceeded`。API 映射为稳定业务码和安全文案；服务端日志记录请求关联 ID、阶段、工具名、参数摘要、耗时、结果数、失败类别和 Tavily request ID，不记录 API Key、完整用户输入或网页正文。

必须获取网络资料时，只要最终证据不足，便不调用出题 Gateway。部分工具失败但剩余证据充分时可以继续，响应仍只包含实际成功的来源。查询规划或最终出题失败沿用 AI 生成失败语义和既有重试预算。

### 9. 前端以增量方式启用 URL 和来源状态

启用首页现有 URL 标签，提供单 URL 输入和基础 HTTP(S) 校验；文本入口和既有生成参数保持不变。生成页按实际路径展示“理解内容”“搜索资料”“提取网页”“核对资料”“生成题目与讲解”等非百分比状态，不伪造服务端实时百分比。

`generateQuiz` 保留可取消的 Taro `RequestTask` 包装，页面卸载或用户取消时调用 `abort()`，并以请求序号阻止旧响应覆盖新请求。错误页按搜索、提取、URL 安全、证据不足和歧义给出对应操作，始终保留原输入。

预览页增加与现有黄色/橙色漫画练习册风格一致的来源概览卡；答题反馈增加本题折叠来源；历史详情复用来源组件。因为 URL 状态和来源卡片不在已确认原型中，实施前必须先更新 `prototype/01-core-flow.html` 并经人工确认。

### 10. 使用兼容字段与 MySQL JSON 快照保存生成依据

为 `quiz_sessions` 增加可空的 `grounding_mode`、`sources_json` 与 `researched_at`，并把每题 `source_ids` 保存在现有 `questions_json` 快照中。来源 JSON 包含获取方式但不保存完整网页正文。增量迁移保存为独立、可重复执行的 SQL 文件，初始化脚本同步最终结构；旧行字段为空时映射为“历史记录未保存来源”。

JSON 快照符合“保存生成当时依据”的审计需求，也避免 MVP 阶段引入来源复用与级联关系。未来若建设长期知识库，再迁移为规范化来源实体。

### 11. 限流、缓存与可观测性保护外部成本

生成接口复用可选鉴权，并按用户 ID（匿名时按现有客户端标识策略）限流。Search 缓存键包含规范化查询、搜索深度、结果数、主题、时间、国家和语言参数；Extract 缓存键包含规范 URL、提取深度和相关查询。时效主题 TTL 默认不超过 10 分钟，URL 正文缓存也必须短期且不能跨越显式刷新请求。

记录每次生成的工具选择序列、搜索次数、提取页面数、有效来源数、各阶段耗时、证据裁剪量和失败类别。指标标签不得包含完整查询、网页正文或用户敏感内容。

## Risks / Trade-offs

- [Agent 工具选择存在不确定性] → 只暴露两个只读工具，提供明确描述和决策 Prompt，并以参数 Schema、调用预算、证据门槛和场景测试约束结果。
- [Tavily 成为外部单点，额度耗尽会阻断主题与 URL 出题] → 独立健康检查、稳定错误码、限流、超时、用量指标和功能开关；不静默降级。
- [Search 后再 Extract 增加延迟和费用] → 简单知识默认只用摘要，复杂知识最多提取 3 页，并限制总调用与上下文预算。
- [城市范围不是 Tavily 原生字段] → 城市写入查询词并使用国家级排序增强，验收地域案例，文档和日志不宣称存在城市过滤。
- [网页资料可能错误、冲突或含提示注入] → 优先第一方或跨站点支持，正文按不可信数据隔离，冲突/歧义时拒绝生成并展示来源。
- [URL 可能泄露内网或凭据] → 前后端分层校验、DNS/IP 分类、重定向复检、私网与凭据 URL 拒绝，并禁止记录完整敏感 URL。
- [LangChain 0.x 到 1.x 升级影响现有 DeepSeek 链] → 先建立回归基线与最小兼容性测试，再单独升级并锁定版本；升级失败可回退依赖提交。
- [新增字段导致旧缓存或历史数据解析失败] → API 只增不删、前端字段可选、数据库列可空，旧记录提供明确展示状态。

## Migration Plan

1. 在当前代码上运行后端、前端和微信小程序构建并保存基线；用隔离测试验证候选 LangChain 1.x、`langchain-deepseek`、`langchain-tavily` 的 Agent 工具调用、原生异步和结构化输出。
2. 先实现并测试关闭状态下的配置、模型兼容字段和可重复 MySQL 增量迁移，确保旧版前端及旧历史仍可运行。
3. 以伪造工具完成研究 Agent、两个适配器、预算、安全、证据和题库生成的 TDD，再使用测试 Key 做受控在线烟雾测试。
4. 更新并人工确认 URL 输入、研究状态、来源和错误状态的 HTML 原型，然后发布兼容新增字段的前端。
5. 在测试环境逐类验收简单、复杂、新颖、URL、中文/英文、城市、时效、歧义、提示注入和工具失败场景，再逐步启用功能开关。
6. 回滚时关闭网络研究开关并回退应用版本；新增可空数据库列可保留。需要网络资料的请求应明确提示能力暂不可用，不能恢复无依据出题。

## Open Questions

- 上线环境的 Tavily 套餐与月度预算可在部署前确定；它只影响限流和告警阈值，不改变本设计的工具和行为契约。
- 第一方域名白名单首版采用通用规则与可配置补充，具体域名可随验收主题扩展，不改变证据门槛。

## Verified References

- [LangChain：Agents](https://docs.langchain.com/oss/python/langchain/agents) — `create_agent`、静态工具、动态工具选择、工具错误 middleware 和迭代停止机制。
- [LangChain：Tavily Search integration](https://docs.langchain.com/oss/python/integrations/tools/tavily_search) — `langchain-tavily`、`TavilySearch`、参数、原生异步和 Agent 用法。
- [LangChain：Tavily Extract integration](https://docs.langchain.com/oss/python/integrations/tools/tavily_extract) — `TavilyExtract`、多 URL、提取深度、失败结果和 Agent 用法。
- [Tavily：Search API](https://docs.tavily.com/documentation/api-reference/endpoint/search) — 搜索深度、结果数、片段、主题、时间、国家与语言参数边界。
- [Tavily：Extract API](https://docs.tavily.com/documentation/api-reference/endpoint/extract) — URL 数量、相关查询、片段数、提取深度、格式与超时边界。
- [LangChain：ChatDeepSeek integration](https://docs.langchain.com/oss/python/integrations/chat/deepseek) — 工具调用、结构化输出和异步能力。
- [Taro：RequestTask](https://docs.taro.zone/docs/apis/network/request/RequestTask) — 微信小程序端 `RequestTask.abort()`。
