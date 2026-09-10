## Context

现有系统是 Taro 4.2.1 + React 18 小程序和 FastAPI + MySQL 后端。用户登录、JWT、题库历史、DeepSeek 结构化出题、Tavily Search/Extract Agent，以及 MySQL 持久化的异步出题任务已经投入使用。新功能必须复用这些边界：登录用户身份来自现有可选/必选鉴权依赖，长耗时操作不阻塞请求，题库结果继续使用当前模型和页面，未提交新字段的客户端行为不变。

当前后端采用 Pydantic 模型、Service 和直接 SQL Repository 分层，没有 ORM 或独立任务队列。开发环境已经有 Java，但没有 LibreOffice、antiword、Chroma 或文档解析 Python 包。见 proposal.md 和本变更的两份 delta spec。

## Goals / Non-Goals

**Goals:**

- 以 MySQL 为业务状态和授权事实来源，以 Chroma 为可重建的向量索引。
- 支持多个用户命名知识库，以及 PDF、DOC、DOCX、Markdown 文档的可靠异步建库。
- 把私有知识检索作为 Agent 工具接入现有出题流程，并在 mixed 模式复用 Tavily。
- 在数据隔离、外部传输、文件路径、删除和失败恢复方面提供可测试的安全边界。
- 按已确认的 `prototype/04-private-knowledge-base.html` 扩展小程序，不重绘现有核心答题页面。
- 所有后端新增行为先写失败测试，完成后运行完整回归。

**Non-Goals:**

- 不做扫描件 OCR、加密 PDF 解密、视频或音频转写。
- 不做知识库共享、团队空间、权限协作、版本对比和在线文档编辑。
- 不引入独立 Celery/Redis 集群；首版沿用进程内后台任务和数据库状态恢复机制。
- 不把 Chroma 作为业务记录数据库，也不允许客户端直接访问 Chroma。
- 不在本变更中修改 XP、判题、报告和微信登录规则。

## Decisions

### 1. MySQL 管状态，Chroma 管可重建索引

新增 `knowledge_bases`、`knowledge_documents` 和 `document_ingestion_tasks` 三张表。MySQL 保存所有权、名称、原文件相对存储键、大小、MIME、SHA-256、处理状态、错误码、片段数、Embedding 模型和时间戳。Chroma 只保存 chunk 文本、外部计算出的向量和最小检索元数据。

选择该方案是因为删除、配额、重试、所有权和任务恢复都需要事务性业务状态；Chroma 的集合或 metadata 不适合作为这些信息的唯一事实来源。备选方案是把全部信息写入 Chroma，但授权查询、分页和状态迁移更脆弱，故不采用。

### 2. 每个用户一个 Chroma collection，知识库和文档使用 metadata 过滤

collection 名称由不可逆的内部用户 ID 派生，例如 `user_<sha256-prefix>`，不包含 openid、昵称或文件名。每个向量 metadata 至少包含 `user_id`、`knowledge_base_id`、`document_id`、`chunk_index`、`page`/`section` 和安全展示文件名；查询必须同时绑定当前用户 collection 和选定知识库 ID。

这在现有单 Embedding 模型场景下比“每个知识库一个 collection”更便于配额、批量检索和模型迁移，同时仍符合用户级物理隔离要求。若以后需要租户级备份，可再切换为每租户独立目录。

### 3. Embedding 通过百炼兼容接口批量调用，向量显式写入 Chroma

后端新增 `EmbeddingGateway` 抽象和百炼实现，使用中国内地端点及 `text-embedding-v4`。调用按批次处理，验证响应条数和向量维度，再通过 Chroma `upsert(ids, embeddings, documents, metadatas)` 写入；不依赖 Chroma 默认 Embedding function。模型名、向量维度和索引版本写入 MySQL，模型改变时要求重新索引，避免混用向量空间。

LangChain/Chroma 当前用法按 Context7 核对为 `chromadb.PersistentClient(path=...)`、collection `upsert/query` 和 metadata `where` 过滤。百炼的请求字段、批量上限及地域端点在编码前再以阿里云中国内地官方文档校验，避免仅依赖旧版 SDK 示例。API Key 只从后端环境变量读取，`.env.example` 只保留占位符。

### 4. 解析器按格式分派，统一输出 LangChain Document

- PDF：按 LangChain 官方知识库教程当前推荐方式使用 pypdf 读取页面并构造 `langchain_core.documents.Document`，拒绝加密文件和无足够可复制文本的扫描 PDF；不使用已停止维护的 `langchain-community` Loader。
- DOCX：使用 docx2txt 提取后构造 `Document`，保留可取得的段落顺序。
- Markdown：UTF-8/UTF-8-SIG 文本读取后构造 `Document`，避免为纯文本格式引入完整 Unstructured 依赖。
- DOC：使用 Apache Tika 解析器，因为当前环境有 Java，而 LibreOffice/antiword 不存在；启动或部署阶段预热并固定 Tika 版本，解析失败返回可操作提示。实现保留 `LegacyDocParser` 接口，部署环境也可配置外部 Tika Server。

所有格式在解析后执行 NUL/控制字符清理、最大字符数限制和“可用文本阈值”判断。文件扩展名、声明 MIME 和 magic signature 三者必须一致到可接受范围，不能只信客户端文件名。

### 5. 分块采用可配置的递归字符分割

使用 `langchain_text_splitters.RecursiveCharacterTextSplitter`，首版默认 `chunk_size=800`、`chunk_overlap=120`，分隔符优先覆盖中文段落、句号、换行和空格。每个 chunk 使用稳定 ID：`kb:{kb_id}:doc:{doc_id}:chunk:{index}:v{index_version}`。PDF 保留页码，Markdown/DOCX 尽可能保留章节标题。

选择字符分割而不是 token 专用分割，是因为中文文档和多模型兼容性更简单；参数进入配置并由检索质量测试保护，后续可按文档类型调整。

### 6. 文档索引采用数据库任务 + 进程内执行器

上传接口只完成流式大小校验、散列计算、安全落盘、数据库记录和任务创建，返回 HTTP 202。后台执行器以受限并发处理 parsing → chunking → embedding → ready，阶段切换写入 MySQL。服务启动时把遗留的 processing 任务恢复为 pending 并重新调度，任务通过条件更新避免重复执行。

与现有出题任务一致，首版不引入 Redis/Celery，从而保持部署简单。代价是多实例并发控制能力有限；Repository 的原子 claim 和幂等 Chroma upsert 保证重复执行不产生重复片段。未来迁移任务队列时 API 和表结构可保持不变。

### 7. 原始文件使用非公开目录和随机存储键

文件路径为 `<UPLOAD_ROOT>/<user-hash>/<document-uuid>/<safe-name>`，`UPLOAD_ROOT` 不挂载为静态资源。显示名称单独存库，路径解析后必须验证仍位于根目录。上传写入临时文件，校验通过后原子移动；失败或取消清理临时文件。删除文档时先标记 deleting，再删向量和文件，最后删/软删记录；失败可重试清理。

保留原文件是用户已确认的需求，也让重建索引和问题排查可行。备选方案是解析后立即删除，但会使模型升级时无法重建，故不采用。

### 8. 三种来源范围保持确定性外壳

`QuizGenerateRequest` 新增可选 `source_scope: web|private|mixed` 和 `knowledge_base_ids: list[int]`：

- 字段缺失：完全沿用当前 `source_type=text|url` 与 ResearchPolicy。
- `web`：显式执行现有公开资料流程。
- `private`：先进行确定性的知识库检索，不注册/调用 Tavily 工具；证据不足则失败。
- `mixed`：必须先执行一次私有检索，再向 Agent 提供“公开搜索/网页提取”工具；Agent 可基于用户主题和私有证据的抽象缺口决定是否联网。

智能路由不能绕过硬边界。Tavily 工具入参由后端清洗器构造，只允许用户原始主题、公开术语和缺口摘要，禁止拼入私有 chunk。Agent 的工具选择仍受现有预算、超时和 URL 安全策略约束。

### 9. 私有来源复用现有 EvidenceSource/题目引用模型

扩展来源 kind/type 支持 `private_document`，稳定 source ID 由 document ID 与逻辑位置生成。对模型提供 chunk 内容，对 API/前端只返回文档显示名、页码/章节、知识库 ID 和必要摘要，不返回磁盘路径、collection 名称或 openid。每道题的 `source_ids` 必须至少包含一个本次检索到的私有来源；mixed 的公开来源继续通过现有证据白名单校验。

完成题库仍整体写入 quiz task `result_json` 和 quiz session `sources_json`，因此删除知识库后历史记录仍可解释。私有原文删除后不再可打开全文，只保留当时用于解释的安全引用快照。

### 10. 检索先做向量 Top-K，再做确定性门槛

每个知识库合并查询，默认取 Top 8，并限制单文档最大命中数以避免一份长文档垄断上下文。距离转换为归一化相关度后应用配置阈值；命中为空、有效字符不足或不足以支持题量时抛出 `PRIVATE_EVIDENCE_INSUFFICIENT`，禁止回退到模型记忆。

首版不额外引入 reranker，以控制延迟和成本。为方便未来升级，Retriever 返回统一的 `RetrievedChunk`，后续可在不改 API 的情况下添加混合关键词检索或重排。

### 11. API 与前端页面

新增 API：

- `POST/GET /api/v1/knowledge-bases`
- `GET/PUT/DELETE /api/v1/knowledge-bases/{kb_id}`
- `POST/GET /api/v1/knowledge-bases/{kb_id}/documents`
- `GET/DELETE /api/v1/knowledge-bases/{kb_id}/documents/{document_id}`
- `POST /api/v1/knowledge-bases/{kb_id}/documents/{document_id}/reindex`

上传和 reindex 返回任务/文档状态；列表和详情提供轮询所需状态。所有接口要求登录。错误使用现有统一响应/异常机制，并增加稳定业务错误码。

Taro 新增知识库列表、创建、详情、上传和处理状态页面；“我的”增加资料库入口，首页在现有输入类型区域增加来源范围和知识库选择。页面继续使用微信原生导航栏，避免胶囊遮挡。上传使用 `Taro.chooseMessageFile` 和 `Taro.uploadFile`，正式编码前根据 Taro 4 与微信官方当前文档核对参数、临时路径生命周期和上传限制。

### 12. TDD 与兼容回归

Repository、配额、所有权、文件校验、解析分派、任务状态机、Embedding 批处理、Chroma 过滤、删除清理、Agent 隐私边界和新 API 均先写失败测试。外部 API、文件解析和 Chroma 使用测试替身或临时目录；另提供需要真实 Key 才运行的 opt-in 烟雾测试。最终必须通过现有全部后端测试、前端测试、TypeScript 检查和微信构建。

## Risks / Trade-offs

- [进程内任务在多实例环境下吞吐有限] → 使用数据库原子 claim、幂等 upsert 和启动恢复；规模增长后可替换为独立 worker。
- [Chroma 本地目录不适合多节点共享写入] → 首版明确单后端实例部署；MySQL 保留重建所需元数据和原件，未来迁移托管向量库。
- [旧版 DOC 的 Tika 运行时和首次启动成本较高] → 固定版本、部署预热、提供外部 Tika Server 配置，并对不可解析文件返回明确错误。
- [百炼或 DeepSeek 外部处理私有片段带来隐私风险] → 上传前明确告知，只发送必要片段，日志脱敏，禁止 Tavily 接收私有内容；后续可增加本地模型选项。
- [文档内提示注入影响 Agent] → 私有和网页片段均作为不可信证据，用系统提示和来源白名单限制工具与输出，不执行文档内指令。
- [删除流程跨 MySQL、文件系统、Chroma 非事务] → 使用 deleting 状态和幂等补偿清理，避免先删数据库导致孤儿资源不可追踪。
- [大文档解析和 Embedding 成本不可控] → 文件/文档/知识库配额、字符和 chunk 上限、Embedding 批量与并发限制，并记录失败原因。
- [Chroma 距离在不同空间中阈值含义不同] → 固定 collection metric 和 Embedding 版本，以带基准语料的检索测试校准阈值。

## Migration Plan

1. 新增依赖和环境变量示例，但保持新功能默认不影响现有请求。
2. 执行可重复的 MySQL 迁移，创建知识库、文档、索引任务表，并给出回滚 SQL/说明。
3. 创建并验证上传目录与 Chroma 持久化目录权限，预热 DOC 解析器。
4. 部署后端知识库 API 和索引执行器；先以测试账户完成 PDF、DOC、DOCX、MD 建库烟雾测试。
5. 部署扩展后的出题任务；验证旧文本、URL、匿名出题，以及 private/mixed 登录出题。
6. 构建并导入 Taro `dist`，人工验收已确认原型的全部状态。

回滚时先停止创建新索引任务并回滚前端入口；旧出题接口不受影响。保留 MySQL 新表、原件和 Chroma 目录以防误删，确认不再需要后再执行独立清理，数据库迁移不自动删除用户资料。
