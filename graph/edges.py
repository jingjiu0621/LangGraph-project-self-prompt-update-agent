"""自提示更新流水线的条件边路由逻辑。

路由函数检查 GraphState 并返回要派发到的下一个节点标签。
路由映射到 plan.md 中的阶段：

    acceptance_router      → 阶段5↺（重新执行）或阶段6（反馈收集）
    evolution_router       → 阶段10（进化提案）或 END
    feedback_quality_router → 阶段7（提取）或回到阶段4（重新执行）
"""

from graph.state import GraphState


def acceptance_router(state: GraphState) -> str:
    """输出格式化后的路由：收集反馈或直接通过。

    返回：
        "collect_feedback" → 阶段6：feedback_collector
        "harvest"          → 跳过反馈，直接进入提取
    """
    # 目前始终收集反馈——流水线总是在学习
    return "collect_feedback"


def feedback_quality_router(state: GraphState) -> str:
    """判断输出是被接受还是需要修改。

    返回：
        "revise"     → 回到 agent_executor 重新执行
        "extract"    → 进入阶段7提取流水线
    """
    feedback_type = state.get("feedback_type", "unknown")

    if feedback_type == "correction":
        revisions = state.get("revision_count", 0)
        if revisions < 3:  # 硬上限：最多 3 次修订循环
            return "revise"

    return "extract"


def evolution_router(state: GraphState) -> str:
    """判断是否触发进化提案或结束。

    返回：
        "evolve" → 阶段10：evolution_checker
        "end"    → END
    """
    eval_results = state.get("eval_results", {})
    completion = eval_results.get("completion_score", 5.0)

    # 仅在质量表明有改进空间时触发进化
    if completion < 3.5:
        return "evolve"

    return "end"
