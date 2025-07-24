from langgraph.graph import StateGraph, END
from .state import ResearchState
from agents.planner import PlannerAgent
from agents.searcher import SearcherAgent
from agents.retriever import RetrieverAgent
from agents.summarizer import SummarizerAgent
from agents.critiquer import CritiquerAgent
from agents.writer import WriterAgent

# Conditional Logic for the Graph

def should_continue_or_end(state: ResearchState) -> str:
    """If no subtopics are generated, end the process."""
    return "searcher" if state.subtopics else END

def should_revise_or_finish(state: ResearchState) -> str:
    """Based on critique, decide to revise the search or finish the report."""
    revision_number = state.revision_number + 1
    if state.needs_revision and revision_number < state.max_revisions:
        print(f"--- Decision: Revising (Attempt {revision_number}) ---")
        # The state is automatically passed to the next node,
        # so we just need to update the revision number.
        state.revision_number = revision_number
        return "searcher"
    else:
        print("--- Decision: Finalizing Report ---")
        return "writer"

def build_research_graph():
    builder = StateGraph(ResearchState)

    # Add all the nodes
    builder.add_node("planner", PlannerAgent)
    builder.add_node("searcher", SearcherAgent)
    builder.add_node("retriever", RetrieverAgent)
    builder.add_node("summarizer", SummarizerAgent)
    builder.add_node("critiquer", CritiquerAgent)
    builder.add_node("writer", WriterAgent)

    # Define the graph flow
    builder.set_entry_point("planner")

    builder.add_conditional_edges(
        "planner",
        should_continue_or_end,
        {
            "searcher": "searcher",
            END: END
        }
    )

    builder.add_edge("searcher", "retriever")
    builder.add_edge("retriever", "summarizer")
    builder.add_edge("summarizer", "critiquer")

    builder.add_conditional_edges(
        "critiquer",
        should_revise_or_finish,
        {
            "searcher": "searcher",  # Loop back for revision
            "writer": "writer"
        }
    )
    
    builder.add_edge("writer", END)

    return builder.compile()