"""Self-Prompt-Update Agent — 全链路 Graph 骨架。

构建并编译 LangGraph StateGraph，定义 11 个 Phase 的节点注册和边拓扑。
具体实现在各 Phase 开发周期中逐步填入，当前仅为最小可编译骨架。
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from graph import (
    GraphState,
    agent_executor,
    context_retriever,
    evaluator,
    event_recorder,
    evolution_checker,
    evolution_router,
    extraction_pipeline,
    feedback_collector,
    feedback_quality_router,
    graph_updater,
    memory_updater,
    output_formatter,
    prompt_compiler,
    reliability_gate_checker,
)


def build_graph() -> StateGraph:
    """构建并编译自提示更新全链路 Graph。

    拓扑结构：
      START → P1 → P2 → P3 → P4 → P5 → P6 ─┬─ revise → P4 (max 3×)
                                              └─ accept → P7 → P8 → P9 → P10 ─┬─ evolve → P11 → P12 → END
                                                                                └─ end → END
    """
    builder = StateGraph(GraphState)

    # ── 注册 12 个 Phase 节点 ──────────────────────────────────────────
    builder.add_node("event_recorder", event_recorder)
    builder.add_node("context_retriever", context_retriever)
    builder.add_node("prompt_compiler", prompt_compiler)
    builder.add_node("agent_executor", agent_executor)
    builder.add_node("output_formatter", output_formatter)
    builder.add_node("feedback_collector", feedback_collector)
    builder.add_node("extraction_pipeline", extraction_pipeline)
    builder.add_node("memory_updater", memory_updater)
    builder.add_node("graph_updater", graph_updater)
    builder.add_node("evaluator", evaluator)
    builder.add_node("evolution_checker", evolution_checker)
    builder.add_node("reliability_gate_checker", reliability_gate_checker)

    # ── 顺序主干：P1 → P2 → P3 → P4 → P5 ──────────────────────────────
    builder.add_edge(START, "event_recorder")
    builder.add_edge("event_recorder", "context_retriever")
    builder.add_edge("context_retriever", "prompt_compiler")
    builder.add_edge("prompt_compiler", "agent_executor")
    builder.add_edge("agent_executor", "output_formatter")

    # ── P5 → P6：输出后收集反馈 ────────────────────────────────────────
    builder.add_edge("output_formatter", "feedback_collector")

    # ── P6 → P4(修正) 或 P7(提取) ─────────────────────────────────────
    builder.add_conditional_edges(
        "feedback_collector",
        feedback_quality_router,
        {"revise": "agent_executor", "extract": "extraction_pipeline"},
    )

    # ── 顺序尾段：P7 → P8 → P9 → P10 ───────────────────────────────────
    builder.add_edge("extraction_pipeline", "memory_updater")
    builder.add_edge("memory_updater", "graph_updater")
    builder.add_edge("graph_updater", "evaluator")

    # ── P10 → P11(进化) 或 END ────────────────────────────────────────
    builder.add_conditional_edges(
        "evaluator",
        evolution_router,
        {"evolve": "evolution_checker", "end": END},
    )

    # ── P11 → P12(门禁) → END ─────────────────────────────────────────
    builder.add_edge("evolution_checker", "reliability_gate_checker")
    builder.add_edge("reliability_gate_checker", END)

    return builder.compile()
