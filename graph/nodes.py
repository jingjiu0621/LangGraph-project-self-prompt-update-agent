"""图节点函数 — 完整的自提示更新流水线。

每个节点接收 (GraphState, llm) 并返回要更新的字段部分字典。
阶段直接映射到 plan.md 中的章节。
"""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage, SystemMessage

from graph.state import GraphState


# ═══════════════════════════════════════════════════════════════════
# 阶段 1 — 事件记录（plan.md §7.1）
# ═══════════════════════════════════════════════════════════════════

def event_recorder(state: GraphState, llm: BaseLanguageModel | None = None) -> dict:
    """将用户输入记录为带有 trace_id 的 interaction_event。"""
    user_input = state.get("user_input", "")
    trace_id = state.get("trace_id", uuid.uuid4().hex[:16])

    event = {
        "trace_id": trace_id,
        "actor": "user",
        "event_type": "user_message",
        "content_text": user_input,
        "visibility": "private",
    }

    return {
        "interaction_event": event,
        "trace_id": trace_id,
        "status": "event_recorded",
    }


# ═══════════════════════════════════════════════════════════════════
# 阶段 2 — 上下文检索（RAG）（plan.md §9）
# ═══════════════════════════════════════════════════════════════════

def context_retriever(state: GraphState, llm: BaseLanguageModel | None = None) -> dict:
    """检索相关上下文：用户画像、项目事实、历史任务、记忆。"""
    user_input = state.get("user_input", "")

    if llm:
        messages = [
            SystemMessage(
                "你是一个检索分析助手。分析用户输入，判断需要哪些上下文信息。"
                "输出 JSON 格式的检索策略，包含：需要检索的用户偏好、项目知识、历史相似任务、相关记忆。"
            ),
            HumanMessage(content=f"用户输入：{user_input}"),
        ]
        response = llm.invoke(messages)
        strategy_hint = response.content
    else:
        strategy_hint = "fallback: no LLM available"

    context = {
        "memories": [],
        "past_tasks": [],
        "user_profile": {"style": "default", "language": "zh"},
        "project_facts": [{"key": "project_phase", "value": "seed"}],
        "strategy_hint": strategy_hint,
        "retrieval_count": 0,
    }

    return {"retrieved_context": context, "status": "context_retrieved"}


# ═══════════════════════════════════════════════════════════════════
# 阶段 3 — Prompt 编译（plan.md §10）
# ═══════════════════════════════════════════════════════════════════

def prompt_compiler(state: GraphState, llm: BaseLanguageModel | None = None) -> dict:
    """从检索到的上下文编译结构化的个性化提示包。"""
    user_input = state.get("user_input", "")
    context = state.get("retrieved_context", {})
    user_profile = context.get("user_profile", {})
    trace_id = state.get("trace_id", "")

    prompt_package = {
        "trace_id": trace_id,
        "system": "你是一个长期协作的 AI 助手，基于用户画像和项目上下文提供个性化服务。",
        "task_contract": {
            "objective": user_input,
            "constraints": [],
            "acceptance_criteria": [],
        },
        "user_profile": user_profile,
        "project_context": context.get("project_facts", []),
        "retrieved_experience": [],
        "reasoning_policy": "medium_complexity",
        "output_spec": {"language": "zh", "verbosity": "balanced"},
    }

    if llm:
        messages = [
            SystemMessage("分析输入和用户画像，填充任务契约中的约束条件和验收标准。"),
            HumanMessage(content=f"任务：{user_input}\n用户画像：{user_profile}"),
        ]
        response = llm.invoke(messages)
        prompt_package["task_contract"]["constraints"] = [response.content]

    return {"compiled_prompt": prompt_package, "status": "prompt_compiled"}


# ═══════════════════════════════════════════════════════════════════
# 阶段 4 — Agent 执行（plan.md Agent Orchestrator）
# ═══════════════════════════════════════════════════════════════════

def agent_executor(state: GraphState, llm: BaseLanguageModel | None = None) -> dict:
    """执行任务：推理 → 工具调用 → 产出结果。"""
    user_input = state.get("user_input", "")
    prompt = state.get("compiled_prompt", {})
    revision = state.get("revision_count", 0)
    feedback_type = state.get("feedback_type", "")
    # 仅在重新执行时增加 revision_count（由 correction 触发）
    if feedback_type == "correction":
        revision += 1

    if llm:
        style_hint = f"\n(Revision #{revision} — address previous feedback: {state.get('feedback', 'none')})" if revision else ""
        messages = [
            SystemMessage(f"执行以下任务，输出完整结果。{style_hint}"),
            HumanMessage(content=f"任务：{user_input}\n提示包：{prompt}"),
        ]
        response = llm.invoke(messages)
        result = response.content
        plan_summary = f"已执行任务，使用模型 {llm.model}"
    else:
        if revision > 0:
            result = (
                f"[Execution Result for: {user_input}] — Revision #{revision}\n\n"
                f"Feedback addressed: {state.get('feedback', '')}\n"
                f"Content expanded with more detail and depth.\n"
                f"Quality improved after revision."
            )
        else:
            result = (
                f"[Execution Result for: {user_input}]\n\n"
                f"(Template fallback — no LLM configured)\n"
                f"Task analyzed, context retrieved, prompt compiled.\n"
                f"Ready for production execution with LLM."
            )
        plan_summary = "fallback execution (no LLM)"

    return {
        "execution_result": result,
        "execution_plan": plan_summary,
        "revision_count": revision,
        "artifacts": [],
        "tool_calls": [],
        "status": "executed",
    }


# ═══════════════════════════════════════════════════════════════════
# 阶段 5 — 输出格式化
# ═══════════════════════════════════════════════════════════════════

def output_formatter(state: GraphState, llm: BaseLanguageModel | None = None) -> dict:
    """将执行结果格式化为最终的面向用户输出。"""
    result = state.get("execution_result", "")
    trace_id = state.get("trace_id", "")

    if llm:
        messages = [
            SystemMessage("对执行结果进行格式化整理，输出整洁清晰的最终版本。"),
            HumanMessage(content=result),
        ]
        response = llm.invoke(messages)
        formatted = response.content
    else:
        formatted = result

    final_output = (
        f"{'='*60}\n"
        f"  OUTPUT  |  trace: {trace_id[:8]}...\n"
        f"{'='*60}\n\n"
        f"{formatted}\n\n"
        f"{'='*60}\n"
        f"  END\n"
        f"{'='*60}"
    )

    return {"final_output": final_output, "status": "output_formatted"}


# ═══════════════════════════════════════════════════════════════════
# 阶段 6 — 反馈收集（plan.md §7.1 / feedback_items）
# ═══════════════════════════════════════════════════════════════════

def feedback_collector(state: GraphState, llm: BaseLanguageModel | None = None) -> dict:
    """收集并解读用户对输出的反馈。"""
    result = state.get("execution_result", "")
    revision = state.get("revision_count", 0)

    if llm:
        messages = [
            SystemMessage(
                "评估以下输出的质量。如果质量合格，回复以 'ACCEPT' 开头；"
                "如果需要修正补充，回复以 'REVISE' 开头并说明原因。"
            ),
            HumanMessage(content=result),
        ]
        response = llm.invoke(messages)
        feedback_text = response.content

        if feedback_text.startswith("REVISE"):
            feedback_type = "correction"
        else:
            feedback_type = "accept"
    else:
        # 回退：第一次始终需要修订，第二次接受
        if revision < 1:
            feedback_text = "REVISE: output too brief, need more detail and depth"
            feedback_type = "correction"
        else:
            feedback_text = "ACCEPT: output quality acceptable after revision"
            feedback_type = "accept"

    return {
        "feedback": feedback_text,
        "feedback_type": feedback_type,
        "status": "feedback_collected",
    }


# ═══════════════════════════════════════════════════════════════════
# 阶段 7 — 提取流水线（plan.md §7.2）
# ═══════════════════════════════════════════════════════════════════

def extraction_pipeline(state: GraphState, llm: BaseLanguageModel | None = None) -> dict:
    """从交互中提取任务元数据、记忆候选和图谱关系。"""
    user_input = state.get("user_input", "")
    output = state.get("execution_result", "")
    feedback = state.get("feedback", "")

    if llm:
        messages = [
            SystemMessage(
                "从以下交互中提取结构化信息。输出 JSON 格式：\n"
                "1. task_metadata: task_type, domain, intent, complexity_score\n"
                "2. memory_candidates: 用户偏好、项目事实、可复用经验\n"
                "3. relation_candidates: 实体关系候选"
            ),
            HumanMessage(content=f"用户：{user_input}\nAI：{output}\n反馈：{feedback}"),
        ]
        response = llm.invoke(messages)
        extraction = response.content
        task_meta = {"raw_extraction": extraction, "task_type": "general", "domain": "unknown"}
        memories = [{"content": extraction[:200], "source": "extraction_pipeline"}]
        relations = []
    else:
        task_meta = {
            "task_type": "general",
            "domain": "unknown",
            "intent": "explore",
            "complexity_score": 0.5,
        }
        memories = [
            {
                "content": f"User interacted on topic: {user_input[:100]}",
                "memory_type": "episodic",
                "confidence": 0.6,
                "source_event": state.get("trace_id", ""),
            }
        ]
        relations = []

    return {
        "task_metadata": task_meta,
        "memory_candidates": memories,
        "relation_candidates": relations,
        "status": "extracted",
    }


# ═══════════════════════════════════════════════════════════════════
# 阶段 8 — 记忆更新（plan.md §6 / §13）
# ═══════════════════════════════════════════════════════════════════

def memory_updater(state: GraphState, llm: BaseLanguageModel | None = None) -> dict:
    """更新长期记忆：合并候选、解决冲突、应用衰退。"""
    candidates = state.get("memory_candidates", [])

    updated = []
    for i, m in enumerate(candidates):
        updated.append({
            "memory_id": f"mem_{state.get('trace_id', '')[:8]}_{i}",
            "content": m.get("content", ""),
            "memory_type": m.get("memory_type", "episodic"),
            "confidence": m.get("confidence", 0.5),
            "scope": "user",
            "status": "active",
        })

    return {
        "updated_memories": updated,
        "conflict_resolutions": [],
        "status": "memory_updated",
    }


# ═══════════════════════════════════════════════════════════════════
# 阶段 9 — 评估（plan.md §12）
# ═══════════════════════════════════════════════════════════════════

def evaluator(state: GraphState, llm: BaseLanguageModel | None = None) -> dict:
    """评估任务结果：通过 AI 评判计算核心指标。"""
    user_input = state.get("user_input", "")
    output = state.get("final_output", "")
    feedback = state.get("feedback", "")
    feedback_type = state.get("feedback_type", "unknown")

    if llm:
        messages = [
            SystemMessage(
                "作为 AI judge，对以下任务输出进行评分（1-5）。输出 JSON 格式：\n"
                "completion_score, style_match_score, relevance_score, rationale"
            ),
            HumanMessage(content=f"请求：{user_input}\n输出：{output}\n反馈：{feedback}"),
        ]
        response = llm.invoke(messages)
        judge = response.content
    else:
        judge = "fallback judge"

    is_accepted = feedback_type == "accept"
    results = {
        "judge_rationale": judge,
        "completion_score": 4.0 if is_accepted else 2.5,
        "style_match_score": 3.5,
        "relevance_score": 4.0,
        "adoption_rate": 1.0 if is_accepted else 0.0,
        "correction_count": 0 if is_accepted else 1,
        "memory_hit_utility": 0.5,
    }

    return {"eval_results": results, "status": "evaluated"}


# ═══════════════════════════════════════════════════════════════════
# 阶段 10 — 进化检查（plan.md §11 / §17）
# ═══════════════════════════════════════════════════════════════════

def evolution_checker(state: GraphState, llm: BaseLanguageModel | None = None) -> dict:
    """检查是否触发 Prompt/Skill 改进的进化提案。"""
    eval_results = state.get("eval_results", {})
    correction_count = eval_results.get("correction_count", 0)
    completion_score = eval_results.get("completion_score", 0)

    if completion_score < 3.0 or correction_count >= 2:
        should_propose = True
        rationale = "质量低于阈值 — 建议 Prompt/Skill 改进"
    else:
        should_propose = False
        rationale = "质量可接受 — 无需进化"

    proposal = {
        "should_propose": should_propose,
        "rationale": rationale,
        "proposal_type": "prompt_update" if should_propose else None,
        "approval_status": "pending" if should_propose else "not_needed",
    }

    return {"evolution_proposal": proposal, "status": "completed"}
