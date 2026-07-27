# Sub-plan: 临床病例数据模型与数据库

> 目标：在现有通用 event / memory / RAG / eval 数据底座上，新增病例判读辅助 Agent 所需的临床数据模型。  
> 执行阶段：Phase 1 只支持合成病例和 mock 证据，不接真实 PHI/ePHI。  
> 依据：`overview.md` 第 2-4 节、`plan.md` 第 5 节、`need.md` 第 2 节。

---

## 1. 模块边界

本模块负责：

1. 定义 clinical schema 和数据库 migration。
2. 保存病例材料、结构化抽取、证据包、辅助草案、医生反馈、评测结果。
3. 保留原文片段与结构化字段的 source mapping。
4. 为 runtime、RAG、memory、evaluation 提供稳定数据接口。

本模块不负责：

1. 实体抽取模型本身。
2. 医学知识内容正确性。
3. 医生评审结论。
4. 真实系统集成。

## 2. 核心实体

| 实体 | 描述 | MVP 是否必须 |
| --- | --- | --- |
| `ClinicalCase` | 一次病例处理任务容器 | 是 |
| `ClinicalDocument` | 病历文本、化验单、影像报告等输入材料 | 是 |
| `CaseSection` | 主诉、现病史、既往史、辅助检查等章节 | 是 |
| `ClinicalEntity` | 症状、体征、疾病、药品、过敏、检查发现 | 是 |
| `ObservationResult` | 检验、生命体征、检查结果的结构化数值 | 是 |
| `ClinicalTimelineEvent` | 带时间归因的病情事件 | 是 |
| `ProblemItem` | 待医生复核的问题列表，不等同诊断 | 是 |
| `EvidenceSource` | 指南、说明书、路径、术语体系来源 | 是 |
| `EvidenceChunk` | 可检索证据片段 | 是 |
| `ClinicalContextPack` | RAG 召回后注入 runtime 的证据包 | 是 |
| `ClinicalAssessmentDraft` | 待医生复核的辅助草案 | 是 |
| `SafetyFlag` | 红旗、拒答、升级复核标记 | 是 |
| `DoctorReview` | 医生接受、修改、驳回、标记危险 | 是 |
| `ClinicalEvalCase` | 评测样本 | 是 |

## 3. 建议新增 migration

创建 `db/migrations/0002_clinical_case_tables.sql`。

```sql
CREATE TABLE clinical_cases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  project_id uuid,
  case_type text,
  specialty text,
  data_mode text CHECK (data_mode IN ('synthetic','deidentified','production')) NOT NULL DEFAULT 'synthetic',
  status text CHECK (status IN ('draft','structured','analyzed','reviewed','archived')) DEFAULT 'draft',
  risk_level text CHECK (risk_level IN ('low','medium','high','critical')) DEFAULT 'medium',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE clinical_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  case_id uuid NOT NULL REFERENCES clinical_cases(id),
  document_type text NOT NULL,
  title text,
  content text,
  content_hash text,
  source_uri text,
  privacy_class text DEFAULT 'synthetic',
  sensitivity numeric DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE case_sections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  case_id uuid NOT NULL REFERENCES clinical_cases(id),
  document_id uuid NOT NULL REFERENCES clinical_documents(id),
  section_type text NOT NULL,
  section_title text,
  text text NOT NULL,
  char_start int,
  char_end int,
  confidence numeric,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE clinical_entities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  case_id uuid NOT NULL REFERENCES clinical_cases(id),
  entity_type text NOT NULL,
  text text NOT NULL,
  normalized_system text,
  normalized_code text,
  normalized_display text,
  attributes jsonb NOT NULL DEFAULT '{}',
  confidence numeric,
  review_status text DEFAULT 'unreviewed',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE entity_source_refs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  entity_id uuid NOT NULL REFERENCES clinical_entities(id),
  document_id uuid REFERENCES clinical_documents(id),
  section_id uuid REFERENCES case_sections(id),
  quote text,
  char_start int,
  char_end int,
  evidence_score numeric,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE observation_results (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  case_id uuid NOT NULL REFERENCES clinical_cases(id),
  observation_type text NOT NULL,
  name text NOT NULL,
  value_text text,
  value_numeric numeric,
  unit text,
  reference_range text,
  abnormal_flag text,
  observed_at timestamptz,
  source_ref jsonb,
  confidence numeric,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE clinical_timeline_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  case_id uuid NOT NULL REFERENCES clinical_cases(id),
  event_type text NOT NULL,
  event_time_text text,
  event_time timestamptz,
  description text NOT NULL,
  source_refs jsonb,
  confidence numeric,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE problem_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  case_id uuid NOT NULL REFERENCES clinical_cases(id),
  problem_text text NOT NULL,
  status text DEFAULT 'active',
  evidence_refs jsonb,
  confidence numeric,
  review_status text DEFAULT 'unreviewed',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE evidence_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  source_type text NOT NULL,
  title text NOT NULL,
  publisher text,
  version text,
  published_at date,
  effective_until date,
  region text,
  specialty text[],
  evidence_level text,
  license_status text DEFAULT 'pending',
  storage_uri text,
  url text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE evidence_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  evidence_source_id uuid NOT NULL REFERENCES evidence_sources(id),
  chunk_text text NOT NULL,
  chunk_type text,
  applicability jsonb DEFAULT '{}',
  citation jsonb DEFAULT '{}',
  embedding vector,
  token_count int,
  status text DEFAULT 'active',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE clinical_assessment_drafts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  case_id uuid NOT NULL REFERENCES clinical_cases(id),
  draft_json jsonb NOT NULL,
  prompt_version text,
  model_version text,
  evidence_refs jsonb,
  safety_status text DEFAULT 'pending',
  review_status text DEFAULT 'unreviewed',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE safety_flags (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  case_id uuid NOT NULL REFERENCES clinical_cases(id),
  draft_id uuid REFERENCES clinical_assessment_drafts(id),
  flag_type text NOT NULL,
  severity text CHECK (severity IN ('low','medium','high','critical')) NOT NULL,
  message text NOT NULL,
  source_refs jsonb,
  status text DEFAULT 'open',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE doctor_reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  case_id uuid NOT NULL REFERENCES clinical_cases(id),
  draft_id uuid REFERENCES clinical_assessment_drafts(id),
  reviewer_id text,
  decision text CHECK (decision IN ('accept','edit','reject','mark_danger','needs_more_info')),
  edited_json jsonb,
  comment text,
  created_at timestamptz NOT NULL DEFAULT now()
);
```

## 4. 硬性数据策略

1. 当前 Phase 1 中 `data_mode='production'` 必须被 runtime policy 阻断。
2. `deidentified` 和 `production` 数据模式必须等 `need.md` 中合规、授权、伦理和临床负责人审批完成后才能启用。
3. 任意向量检索、全文检索和图谱查询必须同时带 `tenant_id`、`project_id` 或 `case_id` scope。
4. 医学 claim 没有 `source_ref` 时不得进入 `clinical_assessment_drafts` 的判断性字段。
5. 高频查询字段必须列化，JSONB 只放扩展属性，避免核心筛选不可控。

## 5. 索引建议

1. `clinical_documents(case_id, document_type)`
2. `clinical_entities(case_id, entity_type)`
3. `observation_results(case_id, observation_type, observed_at)`
4. `problem_items(case_id, status)`
5. `evidence_sources(source_type, specialty, published_at)`
6. `evidence_chunks(evidence_source_id, status)`
7. `doctor_reviews(case_id, created_at desc)`
8. `safety_flags(case_id, severity, status)`

## 6. Dataclass / Pydantic 契约

新增 `packages/common/clinical_schemas.py`，优先定义纯数据结构：

```python
class ClinicalCase: ...
class ClinicalDocument: ...
class CaseSection: ...
class ClinicalEntity: ...
class ObservationResult: ...
class ClinicalTimelineEvent: ...
class ProblemItem: ...
class EvidenceSource: ...
class EvidenceChunk: ...
class ClinicalContextPack: ...
class ClinicalAssessmentDraft: ...
class SafetyFlag: ...
class DoctorReview: ...
```

字段必须包含：

1. `tenant_id`
2. `case_id`
3. `source_refs`
4. `confidence`
5. `review_status`
6. `created_at`

## 7. 数据写入流程

```text
synthetic_case_fixture
  -> clinical_cases
  -> clinical_documents
  -> case_sections
  -> clinical_entities / observation_results / timeline
  -> problem_items
  -> evidence_context_pack
  -> clinical_assessment_drafts
  -> safety_flags
  -> doctor_reviews
  -> clinical_eval_results
```

## 8. 实现步骤

1. 新建 clinical schema 文件。
2. 新建 `0002_clinical_case_tables.sql`。
3. 建立 3-5 条合成病例 fixture。
4. 写 repository 接口，先支持 in-memory 和未来 PostgreSQL 两种实现。
5. 为每条 entity、observation、problem 绑定 source ref。
6. 接入 runtime 的 case snapshot 输入输出。
7. 写最小集成测试。

## 9. 测试计划

单元测试：

1. clinical schema 序列化和反序列化。
2. source ref 必填校验。
3. `data_mode=synthetic` 下不允许出现 PHI 风险标记。
4. observation 数值、单位、参考范围字段完整性。

集成测试：

1. 合成病例可落成 `clinical_cases` 和 `clinical_documents`。
2. 一条实体可追溯到原文片段。
3. 一份草案可追溯到 evidence chunks。
4. 医生 review 可关联 draft 和 case。

## 10. 验收标准

1. 每个结构化字段都有来源或明确 `source_missing_reason`。
2. 每个医学知识片段都有版本和授权状态。
3. 所有病例输出能追踪到 case、document、prompt、model、evidence、review。
4. 当前阶段所有 fixture 明确标记为 `synthetic`。
5. 删除一个 case 时，相关文档、实体、草案、评测样本的处理路径清晰。

## 11. 风险与控制

| 风险 | 控制 |
| --- | --- |
| 抽取结果脱离原文 | 强制 source ref、quote、char span |
| 病例事实误入长期 memory | schema 层区分 case data 与 reusable policy |
| 真实 PHI 混入测试数据 | data_mode、sensitivity scan、fixture review |
| RAG 来源不可审计 | evidence source version + license_status |
| 后续迁移困难 | 第一版保留 tenant/case/project 全部 scope 字段 |
| JSONB 滥用导致关键查询不可控 | 高频查询字段列化，JSONB 只放扩展属性 |
| 模型输出被误存为医学事实 | draft、claim、problem 分表并标注 review_status |
| evidence source 版本漂移 | knowledge_source_versions + effective_until gate |
