# Sub-plan: 临床安全、隐私、权限与治理

> 目标：在病例判读辅助 Agent 中建立 PHI/ePHI、访问控制、审计、删除传播、监管边界和临床安全治理机制。  
> 依据：`overview.md` 边界、`plan.md` 第 12、17 节、`need.md` 第 5 节。

---

## 1. 治理原则

1. 当前阶段不接真实患者数据。
2. 所有病例数据默认敏感。
3. 最小必要原则优先。
4. 医生是唯一临床决策者。
5. 所有输出必须可追溯、可复核、可回滚。
6. 自动进化不能绕过临床安全门禁。

## 2. 数据分类

| 分类 | 示例 | 默认策略 |
| --- | --- | --- |
| `synthetic` | 合成病例 | 可开发、可测试 |
| `public_medical_knowledge` | 公开指南、术语 | 可索引，需版本 |
| `institution_private` | 院内路径 | 机构权限控制 |
| `deidentified_case` | 去标识病例 | 授权范围内使用 |
| `PHI/ePHI` | 姓名、病历号、真实病历 | 当前阶段禁止 |
| `system_internal` | prompt、policy、trace | 系统权限 |

## 3. PHI 检测范围

需要检测：

1. 姓名、身份证、病历号、住院号。
2. 电话、邮箱、地址。
3. 精确日期和地理信息。
4. 医疗保险号。
5. 影像号、检查号。
6. 罕见组合导致重识别的信息。
7. 上传文件 metadata。

## 4. 访问控制

角色：

1. `developer`
2. `clinician_reviewer`
3. `clinical_lead`
4. `data_steward`
5. `auditor`
6. `system_worker`

关键权限：

```text
read_synthetic_case
read_deidentified_case
read_phi_case
write_case
run_clinical_agent
review_draft
export_eval_case
promote_prompt
promote_knowledge_source
view_audit_log
delete_case_data
```

## 5. 审计

必须记录：

1. 病例创建、读取、修改、删除。
2. 文档上传和脱敏结果。
3. 模型调用和 prompt version。
4. RAG 查询和 evidence refs。
5. 草案展示给谁。
6. 医生 review 操作。
7. eval dataset 生成。
8. prompt / policy / knowledge 变更。
9. 权限拒绝和异常访问。

## 6. 删除传播

删除一个 case 必须处理：

1. `clinical_cases`
2. `clinical_documents`
3. `case_sections`
4. `clinical_entities`
5. `observation_results`
6. `problem_items`
7. `clinical_assessment_drafts`
8. `doctor_reviews`
9. `embedding_chunks`
10. `prompt_context_items`
11. `eval_cases`
12. object storage

审计日志保留最小化、脱敏后的处理记录。

## 7. 临床安全事件

新增 `safety_incidents` 概念：

```json
{
  "incident_type": "overreach | missed_red_flag | unsupported_claim | privacy_leakage | wrong_citation",
  "severity": "low | medium | high | critical",
  "case_id": "case_...",
  "draft_id": "draft_...",
  "detected_by": "doctor | evaluator | system",
  "status": "open | investigating | resolved",
  "mitigation": ""
}
```

High/Critical 事件必须：

1. 阻断相关版本晋级。
2. 进入 regression。
3. 生成复盘任务。
4. 通知临床负责人。

## 8. 监管边界

后续进入真实临床前必须判断：

1. 是否属于临床决策支持 CDS。
2. 是否可能构成 SaMD。
3. 是否需要 IRB/伦理审批。
4. 是否需要 BAA/DPA。
5. 是否符合当地医疗数据法规。
6. 是否允许医生看到模型输出。
7. 是否允许任何写回。

如果无法确认，默认按高风险受控研究系统处理。

## 9. 实现步骤

1. 扩展 `packages/governance/privacy.py`，增加 PHI detector。
2. 新增 `packages/governance/clinical_safety.py`。
3. 新增 audit helper。
4. 新增 access control policy。
5. 为 clinical runtime 增加 data_mode gate。
6. 为 RAG source 增加 license gate。
7. 为 eval dataset 增加 privacy gate。
8. 新增 safety incident schema。

## 10. 测试用例

1. 含姓名/电话/病历号样本被 PHI detector 标记。
2. `data_mode=production` 在未授权配置下被拒绝。
3. 未授权 evidence source 不进入 RAG。
4. 被删除 case 不再可检索。
5. safety incident 阻断版本 promote。
6. 医生外角色不能 review clinical draft。

## 11. 验收标准

1. 当前阶段真实 PHI 输入被阻断。
2. 每个草案展示和 review 都有审计。
3. 删除传播路径有测试。
4. 高风险 incident 会进入 regression。
5. 权限拒绝不泄露病例存在性。

## 12. 风险

| 风险 | 控制 |
| --- | --- |
| PHI 进入日志或 embedding | 输入前检测、索引前过滤 |
| 权限串数据 | tenant/project/case filter |
| 删除不彻底 | deletion workflow + audit |
| 监管定位不清 | 默认高风险，禁止生产使用 |
| 医生过度依赖 | UI 和输出强制标注辅助草案 |
