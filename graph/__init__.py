"""Graph 包 — Self-Prompt-Update Agent（plan.md 完整流水线）。"""

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
    # 状态
    "GraphState",          # TypedDict: 全链路 10 阶段状态 schema

    # 阶段 1 — 事件记录
    "event_recorder",      # Node:  记录用户输入，生成 trace_id

    # 阶段 2 — 上下文检索（RAG）
    "context_retriever",   # Node:  混合检索历史记忆、用户画像、项目知识

    # 阶段 3 — Prompt 编译
    "prompt_compiler",     # Node:  编译结构化个性化 Prompt 包

    # 阶段 4 — Agent 执行
    "agent_executor",      # Node:  执行任务：推理→工具调用→产出

    # 阶段 5 — 输出格式化
    "output_formatter",    # Node:  格式化最终用户输出

    # 阶段 6 — 反馈收集
    "feedback_collector",  # Node:  收集/判断用户反馈（接受 | 拒绝 | 修正）

    # 阶段 7 — 提取流水线
    "extraction_pipeline",  # Node:  抽取任务元数据、记忆候选、图谱关系

    # 阶段 8 — 记忆更新
    "memory_updater",      # Node:  更新长期记忆、合并冲突、执行衰退

    # 阶段 9 — 评估
    "evaluator",           # Node:  AI 评判评分（完成度/风格/相关度）

    # 阶段 10 — 进化检查
    "evolution_checker",   # Node:  判断是否触发 Prompt/Skill 进化提案

    # 边 / 路由器
    "acceptance_router",       # Edge:  输出格式化后 → 收集反馈
    "feedback_quality_router", # Edge:  根据反馈类型决定修订或提取
    "evolution_router",       # Edge:  根据评测决定进化提案或结束
]
