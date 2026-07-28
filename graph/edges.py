"""自提示更新流水线的条件边路由逻辑。

路由函数检查 GraphState 并返回要派发到的下一个节点标签。

    feedback_quality_router → accept（提取）或 correction（重新执行）
    evolution_router       → evolution_checker（进化检查）或 END
"""

from graph.state import GraphState


def feedback_quality_router(state: GraphState) -> str:
    """判断输出是被接受还是需要修改。

    返回：
        "revise"     → 回到 agent_executor 重新执行（max 3 次）
        "extract"    → 进入 Phase 7 提取流水线

    实现要点：
      - 读取 state.feedback_type
      - correction + revision_count < 3 → revise
      - 其他情况（accept/reject/preference/bug）→ extract
    """
    # TODO(P1): 接入真实 feedback_type 判断逻辑
    feedback_type = state.get("feedback_type", "unknown")

    if feedback_type == "correction":
        revisions = state.get("revision_count", 0)
        if revisions < 3:
            return "revise"

    return "extract"


def evolution_router(state: GraphState) -> str:
    """判断是否进入进化检查流水线。

    返回：
        "evolve" → Phase 10：evolution_checker
        "end"    → END

    实现要点：
      - 检查 eval_results 是否存在且有效
      - 存在 → evolve（阈值判断交给 evolution_checker）
      - 不存在或空 → end
    """
    # TODO(P6): eval_results 完整后替换为基于质量的路由
    eval_results = state.get("eval_results", {})
    if eval_results.get("completion_score") is not None:
        return "evolve"

    return "end"
