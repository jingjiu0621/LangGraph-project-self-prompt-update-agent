"""Conditional edge routing logic for the self-prompt-update pipeline.

Router functions inspect GraphState and return the label of the next node
to dispatch to.  Routes map to plan.md phases:

    acceptance_router     → Phase 5↺ (re-execute) or Phase 6 (feedback collection)
    evolution_router      → Phase 10 (evolution proposal) or END
    feedback_quality      → Phase 7 (extraction) or back to Phase 4 (re-execution)
"""

from graph.state import GraphState


def acceptance_router(state: GraphState) -> str:
    """Route after output formatting: collect feedback or pass through.

    Returns:
        "collect_feedback" → Phase 6: feedback_collector
        "harvest"          → skip feedback, go directly to extraction
    """
    # Always collect feedback for now — the pipeline always learns
    return "collect_feedback"


def feedback_quality_router(state: GraphState) -> str:
    """Decide whether output is accepted or needs revision.

    Returns:
        "revise"     → back to agent_executor for re-execution
        "extract"    → proceed to Phase 7 extraction pipeline
    """
    feedback_type = state.get("feedback_type", "unknown")

    if feedback_type == "correction":
        revisions = state.get("revision_count", 0)
        if revisions < 3:  # Hard cap: max 3 revision cycles
            return "revise"

    return "extract"


def evolution_router(state: GraphState) -> str:
    """Decide whether to trigger evolution proposal or end.

    Returns:
        "evolve" → Phase 10: evolution_checker
        "end"    → END
    """
    eval_results = state.get("eval_results", {})
    completion = eval_results.get("completion_score", 5.0)

    # Trigger evolution only when quality suggests improvement opportunity
    if completion < 3.5:
        return "evolve"

    return "end"
