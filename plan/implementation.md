# 个性化 Prompt 增强 Agent MVP 实现说明

## 1. 当前实现状态

本轮已从计划层推进到可运行 MVP 骨架，覆盖：

1. FastAPI 应用入口与健康检查。
2. SQLAlchemy 数据模型与 Alembic 初始迁移。
3. 全链路事件账本：conversation、task、interaction event、tool call、artifact。
4. 三层记忆系统：工作记忆、长期记忆、Skill 记忆、证据、冲突、人工确认状态。
5. 置信与衰退：证据权重、半衰期 freshness、记忆注入阈值、冲突阻断。
6. RAG 与 ContextPack：查询改写、RRF/加权重排、候选过滤、上下文分桶、source_map。
7. PromptCompiler：任务契约、用户画像、项目上下文、历史经验、失败警告、Skill 片段、工具策略和输出规范。
8. Evaluation：任务指标、启发式 judge、eval runner、报告输出。
9. 自主进化：任务聚类、Prompt diff、Skill 草案、proposal repository、rollout planner。
10. 可靠性治理：敏感信息扫描、Prompt Injection 检测、ReliabilityGate、SLO、回滚和人工审批要求。
11. 可视化控制台原型：Run Lab、Trace、Memory、RAG、Prompt、Tool、Graph、Evaluation、Release、Governance 已落地到 `frontend/`。

## 2. 关键代码入口

| 模块 | 路径 | 说明 |
| --- | --- | --- |
| 应用入口 | `app/main.py` | 创建 FastAPI app，注册路由，初始化本地数据库 |
| 配置 | `app/core/config.py` | 读取 `.env` 与默认配置 |
| 数据模型 | `app/db/models.py` | MVP 主数据模型 |
| 数据库会话 | `app/db/session.py` | engine、session、init_db |
| Alembic | `app/db/migrations/versions/0001_initial_schema.py` | 初始 schema 迁移 |
| 事件写入 | `app/ingestion/event_writer.py` | conversation/task/event/tool/artifact 写入 |
| 记忆服务 | `app/memory/manager.py` | 记忆提案、确认、拒绝、评分、注入列表 |
| 置信衰退 | `app/memory/decay.py` | evidence、confidence、freshness、memory_score |
| RAG | `app/rag/hybrid_search.py` | 查询计划、RRF、加权重排 |
| ContextPack | `app/rag/context_packer.py` | 上下文分桶、过滤、token 预算 |
| Prompt 编译 | `app/rag/prompt_compiler.py` | 结构化 Prompt 拼装 |
| 评测 | `app/evaluation/runner.py` | eval runner |
| 治理 | `app/core/reliability.py` | ReliabilityGate |
| 安全 | `app/core/security.py` | 敏感信息与 Prompt Injection 扫描 |
| 前端方案 | `frontend-ui-plan.md` | 技术控制台信息架构、页面、组件和开发阶段 |
| 前端原型 | `frontend/index.html` | 可直接打开的静态 Agent Console |

## 3. 已暴露 API

```text
GET  /health

POST /api/conversations
POST /api/tasks
POST /api/events
GET  /api/events/{event_id}
GET  /api/conversations/{conversation_id}/events
POST /api/events/tool-calls
POST /api/events/artifacts

POST /api/memories
GET  /api/memories
PATCH /api/memories/{memory_id}
POST /api/memories/{memory_id}/confirm
POST /api/memories/{memory_id}/reject
POST /api/memories/{memory_id}/evidence
GET  /api/memories/{memory_id}/score
GET  /api/memories/injectable/

GET  /api/graph/nodes
GET  /api/graph/edges
POST /api/graph/nodes
POST /api/graph/edges

POST /api/prompts/compile
POST /api/evaluations/run
POST /api/evolution/proposals
GET  /api/evolution/proposals
```

## 4. 验证结果

已在可访问用户依赖环境中执行：

```text
python -m pytest
```

结果：

```text
28 passed
```

覆盖范围包括：

- 事件 API 创建、读取、列表。
- EventWriter 事件、工具调用、artifact 写入。
- 记忆半衰期、过期阻断、冲突阻断、证据更新。
- ContextPack 分桶、预算、非注入候选过滤。
- PromptCompiler RAG evidence guard。
- Evaluation 指标。
- ReliabilityGate 敏感信息、Prompt Injection、审批、回滚、SLO 门禁。

## 5. 当前实现边界

MVP 当前采用部分 in-memory repository，适合验证闭环，但还不是生产持久化版本：

1. Memory、Graph、Evolution proposal 的 API 当前以 in-memory repository 为主。
2. 向量检索目前实现了检索评分与上下文打包框架，尚未接入真实 embedding provider 和 pgvector 查询。
3. AI judge 当前是启发式实现，后续需要接入真实 LLM structured output。
4. Prompt/Skill 发布已具备 ReliabilityGate，但还需要 ReleaseService 统一管理 active 状态。
5. 管理 UI 尚未实现。

## 6. 下一阶段建议

1. 将 MemoryRepository、GraphRepository、ProposalRepository 落到 PostgreSQL。
2. 接入 embedding client，完成 `vector_chunks` 写入、pgvector 查询和全文检索融合。
3. 接入真实 LLMClient，替换规则版 extractor 和 HeuristicJudge。
4. 增加 ReleaseService，确保 active Prompt/Skill 只能来自 approved proposal。
5. 补充 Alembic 自动生成校验与 PostgreSQL 集成测试。
6. 建立 `tests/eval_cases/` 首批 20-50 个回归案例。
7. 增加 CLI 或管理 UI，用于记忆确认、Prompt 版本、评测报告和事故复盘。
8. 将 `frontend/` 静态原型升级为正式前端工程，并接入 `/api/*` 数据。
