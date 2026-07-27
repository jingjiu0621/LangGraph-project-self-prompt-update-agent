# Sub-plan: 医生复核台与反馈闭环

> 目标：设计医生复核台的信息架构和反馈数据流，让 Agent 输出只能以待审草案形式存在，并将医生反馈转为评测和改进依据。  
> 依据：`plan.md` 第 13、14、15 节，`need.md` 第 3、7 节。

---

## 1. 产品边界

复核台面向医生或授权临床人员，不面向患者。

允许：

1. 查看病例原文和结构化结果。
2. 查看证据引用和草案。
3. 接受、修改、驳回、标记危险。
4. 补充缺失信息标签。
5. 生成评测样本。

禁止：

1. 自动写回正式病历。
2. 自动下医嘱。
3. 自动发送患者消息。
4. 隐藏“AI 草案/需复核”标识。

## 2. 页面结构

### 2.1 Case Workspace

区域：

1. 原始文档。
2. 章节结构。
3. 实体高亮。
4. 时间线。
5. 问题列表。
6. 检查异常。

每个结构化字段点击后显示 source span、confidence、抽取版本。

### 2.2 Evidence Panel

展示：

1. RAG 命中的指南/路径/说明书。
2. 来源标题、发布者、版本、发布日期。
3. 适用人群和地区。
4. 引用片段。
5. 排除来源及原因。

### 2.3 Draft Review Panel

展示：

1. 病例摘要。
2. 问题列表。
3. 关键异常。
4. 鉴别方向。
5. 缺失信息。
6. 红旗风险。
7. 不确定性。
8. 明确“待医生复核”。

### 2.4 Safety Panel

展示：

1. safety critic 结果。
2. 红旗提示。
3. 阻断原因。
4. 是否存在无证据 claim。
5. 是否存在越权诊断/治疗语言。

## 3. 医生操作

| 操作 | 数据含义 |
| --- | --- |
| Accept | 草案对当前辅助场景可接受 |
| Edit | 医生修改后可接受 |
| Reject | 草案不可用 |
| Mark danger | 存在危险或误导 |
| Needs more info | 资料不足 |
| Mark extraction error | 结构化抽取错误 |
| Mark citation error | 证据引用错误 |

## 4. DoctorReview schema

```json
{
  "case_id": "case_...",
  "draft_id": "draft_...",
  "reviewer_id": "doctor_...",
  "decision": "accept | edit | reject | mark_danger | needs_more_info",
  "edited_json": {},
  "error_tags": ["wrong_subject", "missing_red_flag"],
  "comment": "这里是家族史，不是患者当前问题。",
  "confidence": 0.9,
  "created_at": "2026-07-16T00:00:00Z"
}
```

## 5. 反馈流向

```text
DoctorReview
  -> EvaluationReport
  -> RegressionCase candidate
  -> ClinicalMemoryCandidate
  -> PatternCluster input
  -> SafetyIncident if dangerous
```

所有进入长期改进的数据必须脱敏。

## 6. MVP 实现

Phase 1 不一定做完整前端，可以先实现：

1. review API。
2. review schema。
3. mock review fixture。
4. markdown / JSON review report。
5. eval runner 消费 review。

未来再做 React/Next.js 管理台。

## 7. UI 验收标准

1. 医生永远能看到“AI 辅助草案，需复核”。
2. 每个实体和草案 claim 可追溯来源。
3. 医生可一键标记危险。
4. 医生修改不会自动变成规则。
5. review 数据可进入 eval 和 clustering。
6. 不提供自动写回正式病历按钮。

## 8. 测试用例

1. 医生 reject 会降低 draft 评分。
2. mark danger 生成 safety incident。
3. edit 生成 regression candidate。
4. citation error 进入 RAG eval。
5. extraction error 进入 extraction eval。
6. 未授权用户不能 review。

## 9. 风险

| 风险 | 控制 |
| --- | --- |
| 医生误以为是最终诊断 | 页面、字段、导出都标注草案 |
| 反馈噪声进入规则 | candidate + 审批 |
| 复核负担过重 | 高风险优先、信息分层 |
| 过多提醒导致疲劳 | 记录 alert fatigue 指标 |
| 写回误操作 | MVP 不做写回能力 |
