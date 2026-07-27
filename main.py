"""Self-Prompt-Update Agent — Full Pipeline (plan.md Phase 1-10).

Builds, compiles, and runs a LangGraph StateGraph that implements the complete
self-prompt-update cycle defined in plan.md:

    User Input
       │
       ▼
    ┌─ Phase  1: Event Recording ──────► trace_id + interaction_event
    │
    ▼
    ┌─ Phase  2: Context Retrieval ─────► hybrid RAG (memory + profile + project)
    │
    ▼
    ┌─ Phase  3: Prompt Compilation ───► structured prompt package
    │
    ▼
    ┌─ Phase  4: Agent Execution ──────► reasoning → tool calls → result
    │
    ▼
    ┌─ Phase  5: Output Formatting ────► final user-facing output
    │
    ▼
    ┌─ Phase  6: Feedback Collection ──► accept / correction  ←── Loop back
    │   │                                         │              (max 3×)
    │   └── accept ──► continue                    │
    │   └── correction ──► Phase 4 (revise) ───────┘
    ▼
    ┌─ Phase  7: Extraction Pipeline ──► task_metadata + memory_candidates + relations
    │
    ▼
    ┌─ Phase  8: Memory Update ────────► long-term memory merge / conflict / decay
    │
    ▼
    ┌─ Phase  9: Evaluation ───────────► AI judge scores
    │
    ▼
    ┌─ Phase 10: Evolution Check ──────► propose Prompt/Skill improvement or END
    │
    ▼
    END


Each phase is a LangGraph node.  Conditional edges route between phases
based on pipeline state (feedback quality, eval scores, revision count).
"""

from __future__ import annotations

import os
import sys
import uuid

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from graph import (
    GraphState,
    acceptance_router,
    agent_executor,
    context_retriever,
    evaluator,
    event_recorder,
    evolution_checker,
    evolution_router,
    extraction_pipeline,
    feedback_collector,
    feedback_quality_router,
    memory_updater,
    output_formatter,
    prompt_compiler,
)

# ── Configuration ──────────────────────────────────────────────────

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
LLM_MODEL = os.getenv("LLM_MODEL", "")


def create_llm() -> ChatOpenAI | None:
    """Create an LLM instance if API credentials are available."""
    if not LLM_API_KEY or not LLM_MODEL:
        print("  [WARN] LLM_API_KEY or LLM_MODEL not set — falling back to template text")
        return None
    return ChatOpenAI(model=LLM_MODEL, api_key=LLM_API_KEY, base_url=LLM_BASE_URL, temperature=0.7)


def _make_node(fn):
    """Wrap a node function that accepts (state, llm) into (state) only."""
    llm = create_llm()
    def wrapper(state: GraphState) -> dict:
        return fn(state, llm=llm)
    return wrapper


# ── Graph builder ──────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Construct the full self-prompt-update pipeline graph."""
    builder = StateGraph(GraphState)

    # ── Register all 10 Phase nodes ─────────────────────────────────
    builder.add_node("event_recorder", _make_node(event_recorder))
    builder.add_node("context_retriever", _make_node(context_retriever))
    builder.add_node("prompt_compiler", _make_node(prompt_compiler))
    builder.add_node("agent_executor", _make_node(agent_executor))
    builder.add_node("output_formatter", _make_node(output_formatter))
    builder.add_node("feedback_collector", _make_node(feedback_collector))
    builder.add_node("extraction_pipeline", _make_node(extraction_pipeline))
    builder.add_node("memory_updater", _make_node(memory_updater))
    builder.add_node("evaluator", _make_node(evaluator))
    builder.add_node("evolution_checker", _make_node(evolution_checker))

    # ── Sequential spine: Phase 1 → 2 → 3 → 4 → 5 ──────────────────
    builder.add_edge(START, "event_recorder")
    builder.add_edge("event_recorder", "context_retriever")
    builder.add_edge("context_retriever", "prompt_compiler")
    builder.add_edge("prompt_compiler", "agent_executor")
    builder.add_edge("agent_executor", "output_formatter")

    # ── Phase 5 → Phase 6 (via acceptance_router) ───────────────────
    builder.add_conditional_edges(
        "output_formatter",
        acceptance_router,
        {"collect_feedback": "feedback_collector"},
    )

    # ── Phase 6 feedback loop: accept → continue, correction → revise ─
    builder.add_conditional_edges(
        "feedback_collector",
        feedback_quality_router,
        {"revise": "agent_executor", "extract": "extraction_pipeline"},
    )

    # ── Sequential tail: Phase 7 → 8 → 9 ────────────────────────────
    builder.add_edge("extraction_pipeline", "memory_updater")
    builder.add_edge("memory_updater", "evaluator")

    # ── Phase 9 → Phase 10 or END (via evolution_router) ────────────
    builder.add_conditional_edges(
        "evaluator",
        evolution_router,
        {"evolve": "evolution_checker", "end": END},
    )

    # ── Phase 10 → END ──────────────────────────────────────────────
    builder.add_edge("evolution_checker", END)

    return builder.compile()

# ── Runner ─────────────────────────────────────────────────────────

def run_graph(user_input: str, verbose: bool = True) -> dict:
    """Invoke the pipeline with user input and return the final state."""
    graph = build_graph()

    initial_state: GraphState = {
        "user_input": user_input,
        "trace_id": uuid.uuid4().hex[:16],
        "revision_count": 0,
        "status": "started",
    }

    if verbose:
        print(f"\n{'═'*60}")
        print(f"  Self-Prompt-Update Agent  |  trace: {initial_state['trace_id']}")
        print(f"{'═'*60}")
        print(f"  LLM: {LLM_MODEL or 'fallback (no API key)'}")
        print(f"  Base: {LLM_BASE_URL}")
        print(f"  Max recursion: 50 steps")
        print(f"{'─'*60}\n")

        for event in graph.stream(initial_state, {"recursion_limit": 50}):
            for node_name, value in event.items():
                status = value.get("status", "")
                print(f"  ▶ {node_name:25s}  [{status}]")

                # Show key field previews for observability
                if "compiled_prompt" in value:
                    print(f"    {'prompt compiled':30s}")
                if "execution_result" in value:
                    rev = value.get("revision_count", "")
                    preview = value["execution_result"][:60].replace("\n", " ")
                    label = f"result (rev #{rev})" if rev else "result"
                    print(f"    {label+':':20s} {preview}…")
                if "final_output" in value:
                    preview = value["final_output"][:60].replace("\n", " ")
                    print(f"    {'final:':15s} {preview}…")
                if "feedback" in value:
                    fb = value["feedback"][:60].replace("\n", " ")
                    print(f"    {'feedback:':15s} {fb}…")
                if "eval_results" in value:
                    er = value["eval_results"]
                    print(f"    {'scores:':15s} completion={er.get('completion_score')}, "
                          f"style={er.get('style_match_score')}, "
                          f"adoption={er.get('adoption_rate')}")
                if "evolution_proposal" in value:
                    ep = value["evolution_proposal"]
                    print(f"    {'propose:':15s} {ep.get('rationale', '')}")
                print()

    result = graph.invoke(initial_state, {"recursion_limit": 50})
    return result


# ── CLI entry point ───────────────────────────────────────────────

def main() -> None:
    """CLI entry — accepts a user input as argument or falls back to default."""
    user_input = " ".join(sys.argv[1:]) or "Tell me about LangGraph self-prompt-update agent"
    result = run_graph(user_input, verbose=True)
    print(result.get("final_output", "(no output)"))
    print(f"\nRevision cycles: {result.get('revision_count', 0)}  |  "
          f"Evolution proposed: {result.get('evolution_proposal', {}).get('should_propose', False)}")


if __name__ == "__main__":
    main()
