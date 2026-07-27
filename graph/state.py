"""图状态定义。

完整自提示更新 Agent 流水线的 schema，涵盖：
事件记录 → 上下文检索 → Prompt 编译 →
Agent 执行 → 输出 → 反馈 → 提取 → 记忆 → 评估 → 进化。
"""

from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    """在 LangGraph agent 中流动的完整流水线状态。

    字段按流水线阶段分组以便阅读。
    """

    # ── 输入 ─────────────────────────────────────────────────────────
    user_input: str          # 原始用户请求
    trace_id: str            # 全链路可观测性的唯一追踪 ID

    # ── 阶段 1：事件记录 ────────────────────────────────────────────
    interaction_event: dict  # 记录的 interaction_events 行（P1 plan.md）
    conversation_id: str     # 对话分组 ID

    # ── 阶段 2：上下文检索（RAG）────────────────────────────────────
    retrieved_context: dict  # 混合检索结果（P4 plan.md）
    #   { memories: [], past_tasks: [], user_profile: {}, project_facts: [] }

    # ── 阶段 3：Prompt 编译 ─────────────────────────────────────────
    compiled_prompt: dict    # 结构化提示包（P4 / §10 plan.md）
    #   { system, user_profile, project_context, task_contract,
    #     retrieved_experience, tool_policy, reasoning_policy, output_spec }

    # ── 阶段 4：Agent 执行 ──────────────────────────────────────────
    execution_plan: str      # 推理摘要/计划（P1 reasoning_summary）
    tool_calls: list[dict]   # tool_calls 行（P1 plan.md）
    execution_result: str    # Agent 原始输出
    artifacts: list[dict]    # 生成的产物（P1 plan.md）

    # ── 阶段 5：输出 ────────────────────────────────────────────────
    final_output: str        # 格式化后的最终用户输出

    # ── 阶段 6：反馈 ────────────────────────────────────────────────
    feedback: str            # 用户反馈/修正
    feedback_type: str       # accept | reject | correction | preference | bug

    # ── 阶段 7：提取流水线 ──────────────────────────────────────────
    task_metadata: dict      # 提取的任务类型、领域、意图等（P2 / §7.2）
    memory_candidates: list  # 等待审核的记忆草稿（P2 / §7.2）
    relation_candidates: list  # 图谱节点/边候选（P5 / §8）

    # ── 阶段 8：记忆更新 ────────────────────────────────────────────
    updated_memories: list   # 已写入的记忆项（P3 / §6）
    conflict_resolutions: list  # 冲突处理记录（P3 / §6）

    # ── 阶段 9：评估 ────────────────────────────────────────────────
    eval_results: dict       # 评估分数（P6 / §12）
    #   { adoption_rate, completion_rate, correction_rate, memory_hit_utility, ... }

    # ── 阶段 10：进化 ───────────────────────────────────────────────
    evolution_proposal: dict  # Prompt/Skill 改进候选（P7 / §11）
    reliability_gate: dict    # ReliabilityGate 检查结果（§17）

    # ── 循环控制 ─────────────────────────────────────────────────────
    revision_count: int      # 发生了多少次修订循环
    status: str              # 当前阶段标签
