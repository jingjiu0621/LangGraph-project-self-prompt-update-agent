# Sub-plan: 临床反馈聚类、模式提炼与受控进化

> 目标：从医生反馈、评测失败和 safety incident 中提炼可改进的流程、prompt、抽取规则和知识库候选，但禁止自动上线。  
> 依据：`plan.md` 第 14、15、17 节，现有 `packages/evolution/engine.py`。

---

## 1. 进化边界

允许生成候选：

1. prompt 改进候选。
2. extraction rule 候选。
3. safety rule 候选。
4. RAG source gap 候选。
5. evaluation regression case。
6. doctor review pattern。

禁止自动上线：

1. 诊断逻辑。
2. 治疗建议。
3. 药品规则。
4. 安全红线阈值。
5. 医学知识库内容。

所有候选必须经过 eval gate 和临床负责人审批。

候选生命周期：

```text
draft
  -> evaluated
  -> clinical_review
  -> shadow
  -> canary
  -> active
  -> deprecated / rollback
```

Phase 1 只允许停留在 `draft` 或 `evaluated`。

## 2. 聚类输入

| 输入 | 示例 |
| --- | --- |
| `DoctorReview` | 医生修改、驳回、标记危险 |
| `EvalResult` | 结构化失败、RAG 失败、安全失败 |
| `SafetyIncident` | 红线漏报、越权输出 |
| `UnsupportedClaim` | 草案中无证据医学事实 |
| `ExtractionError` | 否定、时间、主体、单位错误 |
| `RAGMiss` | 应召回证据未召回 |

所有输入必须脱敏。

不得进入高质量池：

1. PHI 未脱敏样本。
2. trace 不完整样本。
3. safety 红线失败且未完成复盘样本。
4. 医生驳回但原因未分析样本。
5. 真实数据授权范围不允许复用的样本。

## 3. 聚类维度

1. 错误类型：抽取、RAG、草案、safety、UI。
2. 临床实体类型：症状、药物、过敏、检验、影像。
3. 场景：门诊、住院、急诊、会诊。
4. 人群：成人、儿童、孕产妇、老年。
5. 来源：模型版本、prompt 版本、知识库版本。
6. 医生处理：接受、修改、驳回、标危。

## 4. PatternCandidate 契约

```json
{
  "candidate_type": "extraction_rule | prompt_patch | safety_rule | rag_gap | eval_case",
  "title": "家族史主体识别错误",
  "description": "多次把家族成员疾病误归为患者当前问题。",
  "supporting_events": ["review_...", "eval_..."],
  "proposed_change": "在抽取 prompt 中强制输出 subject 字段，并对 family subject 降级。",
  "risk": "可能漏掉遗传风险提示",
  "required_eval_cases": ["case_..."],
  "status": "draft"
}
```

## 5. 聚类算法 MVP

Phase 1 不需要复杂算法：

1. 规则标签聚类：按 `error_type + entity_type + prompt_version` 聚合。
2. 文本 embedding 聚类：对医生 comment 和失败 rationale 聚类。
3. 支持度过滤：support_count >= 3 才生成候选。
4. 风险过滤：任何 safety incident 单独生成高优先级候选。

## 6. 候选生成流程

```text
collect feedback/eval failures
  -> deidentify
  -> tag error type
  -> cluster
  -> summarize pattern
  -> create candidate
  -> attach evidence
  -> run regression
  -> human approval
  -> versioned rollout or reject
```

## 7. 评分

```text
candidate_score =
  0.25 * support_count_score
+ 0.20 * severity_score
+ 0.15 * recurrence_score
+ 0.15 * fix_feasibility
+ 0.10 * eval_coverage
+ 0.10 * doctor_agreement
+ 0.05 * cost_benefit
- 0.25 * clinical_risk
- 0.20 * overfitting_risk
```

动作：

1. `>=0.85`：进入临床负责人 review。
2. `0.70-0.85`：补充 eval case 后再评。
3. `<0.70`：观察。

## 8. 实现步骤

1. 新增 `packages/evolution/clinical_engine.py`。
2. 定义 `ClinicalPatternCandidate`。
3. 从 doctor reviews 和 eval reports 抽取 failure events。
4. 实现 rule clustering。
5. 实现 candidate summary。
6. 输出 required regression cases。
7. 接入 evaluation gate。
8. 实现 promote/rollback 状态，不自动上线。

## 9. 测试用例

1. 三条相同抽取错误生成一个 candidate。
2. 单条 critical safety incident 生成高优先级 candidate。
3. 含 PHI 的医生 comment 被脱敏后再聚类。
4. 未通过 eval gate 的 candidate 状态为 blocked。
5. candidate 必须有来源事件。
6. promote 必须要求 approval 标记。
7. Phase 1 candidate 不得变成 active。

## 10. 验收标准

1. 候选不含真实患者身份信息。
2. 候选可追溯到 review/eval/safety event。
3. 没有候选能绕过 evaluation 和 human approval。
4. 每个候选说明收益、风险、回滚方式。
5. rejected candidate 保留 tombstone，避免重复提出。
6. 每个候选都有 evidence episode IDs、适用范围、风险评估和 eval report。
7. 进化后必须有可量化收益，且不触发隐私和安全红线。

## 11. 风险

| 风险 | 控制 |
| --- | --- |
| 医生反馈过少导致误聚类 | support_count 和 confidence |
| 候选引入医疗风险 | clinical_risk penalty + 审批 |
| 自动进化越权 | 所有 promote 需要人工 |
| 过拟合少数医生偏好 | 多医生一致性指标 |
| PHI 进入候选 | deidentify + audit |
| 进化漂移偏离临床边界 | safety regression + clinical review |
| 更新后成本和延迟失控 | cost / latency delta gate |
