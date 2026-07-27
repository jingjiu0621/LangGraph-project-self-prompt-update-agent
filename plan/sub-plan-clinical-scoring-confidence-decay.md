# Sub-plan: 临床评分机制、置信度与时间衰减

> 目标：为结构化抽取、证据检索、问题列表、辅助草案、红旗风险、医生反馈和进化候选建立可解释评分。  
> 依据：`plan.md` 第 11、16、17 节，现有 `packages/memory/scoring.py`。

---

## 1. 评分对象

| 对象 | 评分目的 | 输出 |
| --- | --- | --- |
| `ClinicalEntity` | 是否可信、是否需人工复核 | extraction_confidence |
| `ObservationResult` | 数值和单位是否可信 | observation_confidence |
| `ProblemItem` | 是否进入问题列表 | problem_score |
| `EvidenceChunk` | 是否可作为证据 | evidence_score |
| `ClinicalContextPack` | 是否可注入 prompt | context_score |
| `ClinicalAssessmentDraft` | 草案是否可展示给医生 | draft_quality_score |
| `SafetyFlag` | 是否阻断或升级 | safety_severity_score |
| `DoctorReviewPattern` | 是否生成改进候选 | pattern_score |
| `EvalResult` | 是否可信 | eval_confidence |

重要说明：本模块输出的是工程置信与证据质量评分，不是疾病概率、诊断概率或治疗成功概率。UI 和文档中不得把 `confidence` 展示成“患病概率”。

## 2. 基础组件

```text
source_quality_score
extraction_certainty
clinical_relevance
evidence_strength
guideline_applicability
recency_score
doctor_validation_score
conflict_penalty
missing_data_penalty
sensitivity_penalty
overreach_penalty
unsupported_claim_penalty
```

所有组件归一到 `[0, 1]`。惩罚项越高风险越大。

## 3. 抽取置信度

```text
extraction_confidence =
  0.25 * model_confidence
+ 0.20 * source_span_quality
+ 0.15 * section_match_score
+ 0.15 * normalization_score
+ 0.10 * negation_certainty
+ 0.10 * temporal_certainty
+ 0.05 * subject_certainty
- 0.20 * ambiguity_penalty
- 0.20 * ocr_or_transcript_penalty
```

人工复核触发：

1. `extraction_confidence < 0.70`
2. `negation_certainty < 0.75`
3. `subject_certainty < 0.75`
4. 实体属于药物、过敏、红旗风险、关键诊断候选。

## 4. 证据评分

```text
evidence_score =
  0.25 * source_authority
+ 0.20 * applicability
+ 0.15 * recency_score
+ 0.15 * citation_specificity
+ 0.10 * evidence_level_score
+ 0.10 * terminology_match
+ 0.05 * local_policy_priority
- 0.25 * expired_penalty
- 0.20 * region_mismatch_penalty
- 0.20 * population_mismatch_penalty
```

来源权重建议：

| 来源 | source_authority |
| --- | ---: |
| 药品说明书 / 监管文件 | 0.95 |
| 权威指南 | 0.90 |
| 院内路径 | 0.85 |
| 专业学会共识 | 0.80 |
| 教材 / 系统综述 | 0.70 |
| 单篇研究 | 0.45 |
| 普通网页 | 0.10，默认禁用 |

## 5. 问题列表评分

```text
problem_score =
  0.30 * clinical_relevance
+ 0.20 * evidence_from_case
+ 0.15 * abnormal_observation_support
+ 0.15 * temporal_consistency
+ 0.10 * doctor_validation_score
+ 0.10 * safety_importance
- 0.25 * negated_or_historical_penalty
- 0.20 * duplicate_penalty
```

阈值：

1. `>=0.80`：进入问题列表。
2. `0.60-0.80`：进入待复核问题。
3. `<0.60`：不进入，保留抽取日志。

## 6. 草案质量评分

```text
draft_quality_score =
  0.20 * problem_coverage
+ 0.18 * evidence_grounding
+ 0.15 * missing_info_quality
+ 0.15 * red_flag_recall
+ 0.12 * source_attribution
+ 0.10 * uncertainty_expression
+ 0.10 * format_compliance
- 0.30 * overreach_penalty
- 0.25 * unsupported_claim_penalty
- 0.25 * treatment_instruction_penalty
```

展示门槛：

1. `draft_quality_score >= 0.80` 且无红线：可给医生复核。
2. `0.65-0.80`：仅展示结构化摘要和缺失信息，不展示鉴别方向。
3. `<0.65`：拒绝草案，提示资料或证据不足。

## 7. Safety severity score

```text
safety_severity_score =
  max(red_flag_score, overreach_score, evidence_gap_score, privacy_risk_score)
```

动作：

| 分数 | 动作 |
| ---: | --- |
| `>=0.90` | 阻断输出，强制人工接管 |
| `0.75-0.90` | 展示强警告，仅医生可见 |
| `0.50-0.75` | 标注注意事项 |
| `<0.50` | 记录但不阻断 |

红线优先级高于加权平均分：只要出现最终诊断越权、治疗指令、PHI 泄漏、严重红旗漏报或无证据医学 claim，即使 `draft_quality_score` 很高，也必须 fail。

## 8. 时间衰减

```text
recency_score = exp(-ln(2) * age_days / half_life_days)
```

推荐半衰期：

| 对象 | 半衰期 | 说明 |
| --- | ---: | --- |
| 当前病例工作状态 | 1 天 | 任务关闭即失效 |
| 检验参考范围 | 180 天 | 需随机构配置更新 |
| 院内路径 | 90 天 | 有版本和审批 |
| 临床指南 | 365 天 | 以 effective_until 为准 |
| 药品安全警示 | 30 天 | 高时效 |
| 医生格式偏好 | 180 天 | 相对稳定 |
| 抽取错误 pattern | 120 天 | 随模型版本变化 |
| 模型评测结果 | 30 天 | 模型更新后快速过期 |

## 9. 置信校准

校准来源：

1. 医生接受、修改、驳回。
2. 专家 gold label。
3. safety incident。
4. 回归测试结果。
5. 多 evaluator 分歧。

更新规则：

```text
calibrated_confidence =
  raw_confidence
  + 0.10 * doctor_accept_signal
  - 0.20 * doctor_reject_signal
  - 0.25 * safety_incident_signal
  - 0.15 * evaluator_disagreement
```

## 10. 实现步骤

1. 新增 `packages/evals/clinical_scores.py` 或 `packages/memory/clinical_scoring.py`。
2. 定义 `ClinicalScoreComponents`。
3. 实现 entity、evidence、problem、draft、safety 五类评分。
4. 将组件写入 eval report 或 score table。
5. 接入 safety critic。
6. 接入医生 review 后的校准。
7. 为阈值配置添加版本号。

## 11. 测试用例

1. 否定症状不应高分进入问题列表。
2. 过期指南 evidence_score 降低。
3. 无证据草案 unsupported_claim_penalty 高。
4. 含处方建议草案被 treatment_instruction_penalty 阻断。
5. 医生驳回后 pattern confidence 降低。
6. 模型版本变化后相关 pattern recency 下降。

## 12. 验收标准

1. 每个分数都能解释组件。
2. 每次阻断都有可读原因。
3. 阈值可配置、可版本化、可回滚。
4. 医生反馈能改变后续评分。
5. 红线样本不会因平均分高而放行。
6. 对外展示使用“高/中/低置信 + 不确定性原因”，不展示为诊断概率。

## 13. 风险

| 风险 | 控制 |
| --- | --- |
| 平均分掩盖红线 | safety severity 使用 max gate |
| 模型置信虚高 | 医生反馈和 gold set 校准 |
| 旧指南误用 | effective_until + recency + expired_penalty |
| 医生反馈样本偏少 | eval_confidence 标注低置信 |
| 评分公式过拟合 | 回归集和人工抽检 |
| 置信分被误读为临床概率 | 命名、UI 和文档强制说明 |
| 加权平均掩盖关键冲突 | redline max gate 优先 |
