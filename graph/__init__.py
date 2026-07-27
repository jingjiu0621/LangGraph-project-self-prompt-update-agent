"""Graph package — Self-Prompt-Update Agent (plan.md full pipeline)."""

from graph.state import GraphState
from graph.nodes import (
    agent_executor,
    context_retriever,
    evaluator,
    event_recorder,
    evolution_checker,
    extraction_pipeline,
    feedback_collector,
    memory_updater,
    output_formatter,
    prompt_compiler,
)
from graph.edges import acceptance_router, evolution_router, feedback_quality_router

__all__ = [
    # State
    "GraphState",          # TypedDict: 全链路 10-Phase 状态 schema

    # Phase 1 — Event Recording
    "event_recorder",      # Node:  记录用户输入，生成 trace_id

    # Phase 2 — Context Retrieval (RAG)
    "context_retriever",   # Node:  混合检索历史记忆、用户画像、项目知识

    # Phase 3 — Prompt Compilation
    "prompt_compiler",     # Node:  编译结构化个性化 Prompt 包

    # Phase 4 — Agent Execution
    "agent_executor",      # Node:  执行任务：推理→工具调用→产出

    # Phase 5 — Output Formatting
    "output_formatter",    # Node:  格式化最终用户输出

    # Phase 6 — Feedback Collection
    "feedback_collector",  # Node:  收集/判断用户反馈 (accept | reject | correction)

    # Phase 7 — Extraction Pipeline
    "extraction_pipeline",  # Node:  抽取任务元数据、记忆候选、图谱关系

    # Phase 8 — Memory Update
    "memory_updater",      # Node:  更新长期记忆、合并冲突、执行衰退

    # Phase 9 — Evaluation
    "evaluator",           # Node:  AI judge 评分 (completion/style/relevance)

    # Phase 10 — Evolution Check
    "evolution_checker",   # Node:  判断是否触发 Prompt/Skill 进化提案

    # Edges / Routers
    "acceptance_router",       # Edge:  输出格式化后 → 收集反馈
    "feedback_quality_router", # Edge:  根据反馈类型决定修订或提取
    "evolution_router",       # Edge:  根据评测决定进化提案或结束
]
