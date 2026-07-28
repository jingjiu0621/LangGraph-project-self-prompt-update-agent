"""图状态定义。

完整自提示更新 Agent 流水线的 schema，涵盖：
事件记录 → 上下文检索 → Prompt 编译 →
Agent 执行 → 输出 → 反馈 → 提取 → 记忆 → 评估 → 进化。
"""

from __future__ import annotations

from typing import Any, TypedDict


class ReliabilityGateResult(TypedDict, total=False):
    """ReliabilityGate 检查结果（plan.md §17）。

    所有 Prompt/Skill/高影响记忆发布前必须通过。
    """
    passed: bool                     # 是否全部通过
    scope_check: dict                # scope 隔离检查
    sensitivity_check: dict          # 敏感信息扫描
    injection_check: dict            # Prompt Injection 检测
    regression_check: dict           # 回归评测检查
    slo_error_budget: dict           # SLO/error budget 状态
    blockers: list[str]              # 未通过项列表


class GraphState(TypedDict, total=False):
    """在 LangGraph agent 中流动的完整流水线状态。

    字段按流水线阶段分组以便阅读。
    """

    # ── 输入 ─────────────────────────────────────────────────────────
    user_input: str          # 原始用户请求
    trace_id: str            # 全链路可观测性的唯一追踪 ID

    # ── 阶段 1：事件记录（plan.md §7.1）─────────────────────────────
    interaction_event: dict  # 记录的 interaction_events 行
    conversation_id: str     # 对话分组 ID，在 event_recorder 中生成

    # ── 阶段 2：上下文检索 / RAG（plan.md §9）───────────────────────
    retrieved_context: dict  # 混合检索结果
    #   { memories: [], past_tasks: [], user_profile: {}, project_facts: [],
    #     strategy_hint: str, retrieval_count: int }

    # ── 阶段 3：Prompt 编译（plan.md §10）────────────────────────────
    compiled_prompt: dict    # 结构化提示包
    #   { system, user_profile, project_context, task_contract,
    #     retrieved_experience, tool_policy, reasoning_policy, output_spec }

    # ── 阶段 4：Agent 执行（plan.md Agent Orchestrator）──────────────
    execution_plan: str      # 推理摘要/计划（P1 reasoning_summary）
    tool_calls: list[dict]   # tool_calls 行（P1）
    execution_result: str    # Agent 原始输出
    artifacts: list[dict]    # 生成的产物（P1）

    # ── 阶段 5：输出 ────────────────────────────────────────────────
    final_output: str        # 格式化后的最终用户输出

    # ── 阶段 6：反馈收集（plan.md §7.1 / feedback_items）────────────
    feedback: str            # 用户反馈/修正
    feedback_type: str       # accept | reject | correction | preference | bug

    # ── 阶段 7：提取流水线（plan.md §7.2）───────────────────────────
    task_metadata: dict      # 提取的任务类型、领域、意图等
    memory_candidates: list  # 等待审核的记忆草稿
    relation_candidates: list  # 图谱节点/边候选（供 Phase 10 使用）

    # ── 阶段 8：记忆更新（plan.md §6 / §13）─────────────────────────
    updated_memories: list   # 已写入的记忆项
    conflict_resolutions: list  # 冲突处理记录

    # ── 阶段 9：图谱更新（plan.md §5.6 / §8）────────────────────────
    graph_nodes: list[dict]  # 更新的图谱节点（归一化后）
    graph_edges: list[dict]  # 更新的图谱边（含置信度、证据链）

    # ── 阶段 10：评估（plan.md §12）─────────────────────────────────
    eval_results: dict       # 评估分数
    #   { adoption_rate, completion_rate, correction_rate,
    #     memory_hit_utility, completion_score, style_match_score, ... }

    # ── 阶段 11：进化与发布门禁（plan.md §11 / §17）───────────────
    evolution_proposal: dict    # Prompt/Skill 改进候选
    reliability_gate: ReliabilityGateResult  # ReliabilityGate 检查结果
    evolution_approved: bool    # 是否通过审批（人工或自动）

    # ── 循环控制 ─────────────────────────────────────────────────────
    revision_count: int      # 当前修订循环次数
    status: str              # 当前阶段标签
