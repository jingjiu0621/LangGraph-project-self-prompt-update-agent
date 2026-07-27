# Sub-plan: 临床 Memory 架构与病例上下文管理

> 目标：为病例判读辅助 Agent 建立安全的短期病例工作记忆、项目/机构流程记忆、医生反馈记忆，避免患者事实污染长期个性化记忆。  
> 依据：`plan.md` 第 10 节、`need.md` 第 5 节、现有 `packages/memory` scaffold。

---

## 1. 关键原则

1. 当前病例事实默认只属于 L1 工作记忆。
2. 真实患者信息不得进入通用 L3。
3. 医生反馈可以脱敏后进入候选改进规则，但不能自动上线。
4. 院内路径、科室偏好、复核流程属于 L2 项目/机构记忆。
5. 患者纵向记忆必须等合规、授权和 EMR 集成完成后才允许设计。

## 2. Memory 分层

| 层级 | 名称 | 内容 | 生命周期 | 默认写入 |
| --- | --- | --- | --- | --- |
| L1 | 当前病例工作记忆 | 当前病例材料、结构化结果、问题列表、证据包、草案状态 | case/run 级 | 自动 |
| L2 | 项目/机构记忆 | 目标科室、院内路径、输出模板、红旗规则、评测阈值 | project/tenant 级 | 管理员确认 |
| L3 | 医生/机构反馈记忆 | 医生稳定修改模式、常见抽取错误、格式偏好 | 脱敏长期 | 候选 + 审批 |
| Patient | 患者纵向记忆 | 过敏、慢病、长期用药、历史就诊 | 暂不实现 | 禁止 |

## 3. Memory 类型

```text
case_working_state
case_problem_snapshot
evidence_context_snapshot
safety_flag_snapshot
institutional_workflow_rule
specialty_output_template
clinical_safety_rule
doctor_review_pattern
common_extraction_error
common_rag_failure
evaluation_regression_seed
```

禁止类型：

```text
patient_identity_fact
raw_patient_record
unreviewed_diagnosis
unreviewed_treatment_rule
single_patient_cross_case_pattern
```

## 4. 写入策略

### 4.1 L1 自动写入

写入内容：

1. 当前 `ClinicalCase` 的 case snapshot。
2. 当前结构化实体和问题列表摘要。
3. 当前 RAG evidence pack 的 source id 列表。
4. 当前 safety flags。
5. 当前 draft 和 review 状态。

退出条件：

1. case 关闭。
2. 医生 review 完成。
3. run 失败或撤销。

L1 可以落库，但不得作为跨病例检索默认来源。

### 4.2 L2 项目/机构记忆

可写入：

1. 目标科室输出模板。
2. 院内路径和质控规则。
3. 红旗风险清单。
4. 合成数据阶段配置。
5. 评测阈值和验收口径。

写入门槛：

1. 必须有管理员或临床负责人来源。
2. 必须有版本号。
3. 必须有适用范围。

### 4.3 L3 医生反馈记忆

候选来源：

1. 多名医生重复修改同一类草案。
2. 同一医生多次标注同一类抽取错误。
3. safety incident 复盘。
4. 回归评测稳定失败样本。

自动上线：禁止。

候选必须进入 `memory_reviews` 或后续 doctor review console。

### 4.4 写入门禁

1. `patient_identity_fact`、`raw_patient_record`、`unreviewed_diagnosis` 永远禁止写入跨病例 memory。
2. `data_mode=production` 的任何 memory 写入当前阶段必须被 policy 阻断。
3. `sensitivity >= 0.70` 默认禁止长期写入。
4. `conflict_penalty >= 0.60` 必须进入人工 review。
5. L2/L3 memory 必须显式包含 specialty、case_type、institution/project scope，避免跨科室误用。

## 5. MemoryCandidate 契约

```json
{
  "memory_type": "common_extraction_error",
  "level_hint": "L3",
  "content": "模型容易把家族史中的疾病误抽为患者当前问题，结构化抽取时需检查 subject=family。",
  "scope": {
    "tenant_id": "tenant_...",
    "project_id": "proj_...",
    "specialty": "general",
    "task_types": ["clinical_extraction"]
  },
  "sources": [
    {
      "source_type": "doctor_review",
      "source_id": "review_...",
      "quote": "这里是母亲病史，不是患者诊断"
    }
  ],
  "confidence": 0.74,
  "sensitivity": 0.05,
  "requires_human_approval": true
}
```

## 6. 读取策略

读取优先级：

1. 当前用户显式请求和当前病例材料。
2. L1 当前病例工作记忆。
3. L2 项目/机构规则。
4. 受控 RAG evidence。
5. 已审批 L3 医生/机构反馈模式。

不得读取：

1. 其他患者病例。
2. 未授权项目病例。
3. 未审批 L3 候选。
4. 已删除或归档 memory。

## 7. 上下文压缩

进入 prompt 前压缩为：

```json
{
  "case_context": ["当前病例已抽取的问题列表..."],
  "institution_rules": ["输出不得形成最终诊断..."],
  "approved_review_patterns": ["注意区分家族史和患者当前问题..."],
  "blocked_context": [
    {
      "source_id": "mem_...",
      "reason": "contains_patient_specific_fact"
    }
  ],
  "source_ids": ["mem_...", "review_..."]
}
```

## 8. 实现步骤

1. 新增 `packages/memory/clinical_memory.py`。
2. 定义 `ClinicalMemoryPolicy`。
3. 扩展 sensitivity 检测，增加 PHI 和病例事实标记。
4. 实现 `propose_clinical_memory_candidates(DoctorReview | EvalFailure)`。
5. 实现 L1 case snapshot 存取。
6. 实现 L2 rule retrieval。
7. 实现 L3 candidate review gate。
8. 接入 `clinical_runtime.py`。

## 9. 测试用例

1. 当前病例实体只能进入 L1，不能进入 L3。
2. 医生多次修改可生成 L3 candidate，但状态为 candidate。
3. 未审批 candidate 不进入 prompt。
4. 已删除 memory 不进入 RAG。
5. 院内路径 memory 必须带版本和适用范围。
6. 含患者姓名或号码的内容被 sensitivity gate 阻断。

## 10. 验收标准

1. 任何 clinical memory 都能解释来源。
2. 任何跨病例复用 memory 都不含患者身份或单病例敏感事实。
3. L3 自动上线为 0。
4. prompt context 中 memory source id 完整。
5. 删除或驳回的 memory 不再被重复抽取。

## 11. 风险与控制

| 风险 | 控制 |
| --- | --- |
| 患者事实污染长期记忆 | L1/L2/L3/Patient scope 强隔离 |
| 医生一次性修改被过度稳定化 | support_count、时间跨度、人工审批 |
| 机构路径过期 | version、effective_until、临床负责人审批 |
| 记忆覆盖当前病例事实 | 当前病例材料优先级最高 |
| 删除传播不完整 | memory、embedding、graph、context item 联动删除 |
| L2/L3 scope 过宽造成跨科室误用 | specialty、case_type、institution scope 必填 |
| 医生反馈被错误泛化 | 多医生一致性和 review gate |
