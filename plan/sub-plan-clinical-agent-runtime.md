# Sub-plan: 临床 Agent Runtime、Prompt 与 Safety Critic

> 目标：把现有通用 `AgentRuntime` 改造成病例判读辅助流程的可追踪状态机。  
> 依据：`plan.md` 第 6、7、8、15 节，现有 `packages/agent_runtime/runtime.py`。

---

## 1. 模块边界

Runtime 负责：

1. 串起病例输入、脱敏、结构化、RAG、草案生成、安全检查、医生复核、评测。
2. 调用 clinical intake、clinical NLP、clinical RAG、memory、evaluation。
3. 记录 trace、prompt version、model version、context pack。
4. 执行失败降级和拒答。

Runtime 不负责：

1. 真实临床判断。
2. 医生复核结论。
3. 医学知识内容审核。
4. 真实 EMR 写回。

## 2. 状态机

```text
intake
  -> deidentify
  -> classify_documents
  -> structure_case
  -> normalize_entities
  -> build_problem_list
  -> triage_safety
  -> retrieve_evidence
  -> draft_assessment
  -> safety_critic
  -> doctor_review_pending
  -> persist_feedback
  -> evaluate
```

输入安全流程：

1. intake 前检查 `data_mode`，当前阶段只允许 `synthetic`。
2. 对病例文本执行 PHI/ePHI 检测。
3. 对上传文档执行 prompt injection 检测，病历内容永远视为不可信文本。
4. 未通过安全准入时直接阻断，不进入模型和 embedding。

Phase 1 中 `doctor_review_pending` 只写入 mock review 或等待人工。

## 3. RuntimeRequest

```json
{
  "tenant_id": "tenant_...",
  "project_id": "proj_...",
  "case_id": "case_...",
  "data_mode": "synthetic",
  "documents": [
    {
      "document_type": "history",
      "content": "合成病例文本"
    }
  ],
  "runtime_version": {
    "prompt_version": "clinical_draft_v0",
    "rag_policy_version": "clinical_rag_v0",
    "safety_policy_version": "clinical_safety_v0",
    "evaluator_version": "clinical_eval_v0"
  }
}
```

## 4. Prompt 分层

Prompt 顺序：

1. System safety policy。
2. 当前任务边界：只做辅助草案。
3. 当前病例结构化结果。
4. RAG evidence pack。
5. L2/L3 已审批规则。
6. 输出 schema。
7. 禁止项和拒答条件。

当前病例事实优先于历史经验，证据不足优先于生成完整答案。

## 5. 输出 schema

```json
{
  "case_summary": "",
  "problem_list": [],
  "key_abnormalities": [],
  "differential_directions": [
    {
      "direction": "",
      "supporting_evidence": [],
      "against_evidence": [],
      "evidence_sources": [],
      "uncertainty": ""
    }
  ],
  "missing_information": [],
  "red_flags": [],
  "doctor_review_required": true,
  "limitations": []
}
```

## 6. Safety Critic

必须检查：

1. 是否出现最终诊断。
2. 是否出现处方、医嘱、治疗指令。
3. 是否缺少证据引用。
4. 是否无视红旗风险。
5. 是否错误处理否定、时间、主体。
6. 是否把家族史当患者当前问题。
7. 是否对患者直接建议。
8. 是否包含 PHI 泄漏。
9. 是否使用过期或未授权知识源。
10. 是否在证据冲突时强行给出单一判断。
11. 是否缺少 `doctor_review_required=true`。

动作：

1. `pass`：进入医生复核。
2. `warn`：展示强提示并进入医生复核。
3. `block`：不展示草案，只展示原因和需人工处理。

## 7. ModelGateway 接入

MVP 可以先 mock；正式实现必须支持：

1. structured output。
2. prompt version logging。
3. model version logging。
4. cost/latency tracing。
5. PHI filter。
6. retry 和降级。

高风险输出和 safety critic 不应使用同一个模型作为唯一判断。

## 8. 实现步骤

1. 新增 `packages/agent_runtime/clinical_runtime.py`。
2. 定义 `ClinicalRuntimeRequest` / `ClinicalRuntimeResponse`。
3. 新增 mock document classifier。
4. 新增 mock clinical extractor。
5. 接入 clinical RAG mock source。
6. 实现 draft renderer。
7. 实现 safety critic rule v0。
8. 写 trace writer。
9. 接入 clinical evaluator。
10. 写集成测试。

## 9. 测试用例

1. 合成病例可跑完整状态机。
2. 输出包含 doctor_review_required。
3. 出现“诊断为”被 safety critic 阻断。
4. 出现“建议使用某药”被阻断。
5. 无 evidence source 时不能生成鉴别方向。
6. prompt injection 文本不改变系统规则。
7. trace 包含每个状态节点。

## 10. 验收标准

1. 单条合成病例可生成结构化结果、证据包、草案、安全报告、eval report。
2. 所有状态有 trace。
3. 所有草案有 prompt version 和 evidence refs。
4. safety critic 红线失败会阻断。
5. 没有医生复核时，草案状态为 `unreviewed`。
6. 输出必须带 `doctor_review_required=true`。
7. Phase 0/1 不处理真实 PHI/ePHI，不接入 HIS/EMR/LIS/PACS。
8. repair loop 有上限，失败后交付安全降级结果。

## 11. 风险

| 风险 | 控制 |
| --- | --- |
| Runtime 生成越权结论 | safety prompt + critic + redline eval |
| 结构化错误继续传播 | confidence + source ref + review_status |
| RAG 无证据仍生成 | evidence gate |
| 模型自评偏袒 | 独立 critic + human review |
| 成本失控 | mock first、模型路由、离线批处理 |
| 上传病历中的 prompt injection 被执行 | 文档内容作为不可信数据处理 |
| 否定、时间、主体识别错误导致含义反转 | extraction confidence + safety check |
| 医生复核被绕过 | runtime 状态和 UI 均要求 review |
