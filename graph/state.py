"""Graph state definition.

Schema for the full self-prompt-update agent pipeline, covering:
event recording → context retrieval → prompt compilation →
agent execution → output → feedback → extraction → memory → eval → evolution.
"""

from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    """Full pipeline state flowing through the LangGraph agent.

    Fields are grouped by pipeline phase for readability.
    """

    # ── Input ────────────────────────────────────────────────────────
    user_input: str          # Raw user request
    trace_id: str            # Unique trace for full-link observability

    # ── Phase 1: Event Recording ─────────────────────────────────────
    interaction_event: dict  # Recorded interaction_events row (P1 plan.md)
    conversation_id: str     # Conversation grouping ID

    # ── Phase 2: Context Retrieval (RAG) ─────────────────────────────
    retrieved_context: dict  # Hybrid retrieval result (P4 plan.md)
    #   { memories: [], past_tasks: [], user_profile: {}, project_facts: [] }

    # ── Phase 3: Prompt Compilation ──────────────────────────────────
    compiled_prompt: dict    # Structured prompt package (P4 / §10 plan.md)
    #   { system, user_profile, project_context, task_contract,
    #     retrieved_experience, tool_policy, reasoning_policy, output_spec }

    # ── Phase 4: Agent Execution ─────────────────────────────────────
    execution_plan: str      # Reasoning summary / plan (P1 reasoning_summary)
    tool_calls: list[dict]   # tool_calls rows (P1 plan.md)
    execution_result: str    # Agent raw output
    artifacts: list[dict]    # Produced artifacts (P1 plan.md)

    # ── Phase 5: Output ──────────────────────────────────────────────
    final_output: str        # Formatted final output to user

    # ── Phase 6: Feedback ────────────────────────────────────────────
    feedback: str            # User feedback / correction
    feedback_type: str       # accept | reject | correction | preference | bug

    # ── Phase 7: Extraction Pipeline ─────────────────────────────────
    task_metadata: dict      # Extracted task type, domain, intent, etc. (P2 / §7.2)
    memory_candidates: list  # Draft memories awaiting review (P2 / §7.2)
    relation_candidates: list  # Graph node/edge candidates (P5 / §8)

    # ── Phase 8: Memory Update ───────────────────────────────────────
    updated_memories: list   # Memory items written (P3 / §6)
    conflict_resolutions: list  # Conflict handling records (P3 / §6)

    # ── Phase 9: Evaluation ──────────────────────────────────────────
    eval_results: dict       # Eval scores (P6 / §12)
    #   { adoption_rate, completion_rate, correction_rate, memory_hit_utility, ... }

    # ── Phase 10: Evolution ──────────────────────────────────────────
    evolution_proposal: dict  # Prompt/Skill improvement candidate (P7 / §11)
    reliability_gate: dict    # ReliabilityGate check result (§17)

    # ── Cycle control ────────────────────────────────────────────────
    revision_count: int      # How many revision cycles occurred
    status: str              # Current phase label
