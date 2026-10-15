from typing import List
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableLambda
from config import LLM_CRITIQUER, MAX_FOLLOW_UP_QUERIES, MAX_TOTAL_SUBTOPICS
from tools.llm import invoke_structured
from tools.prompts import critique_prompt, escape_untrusted
from graph.state import ResearchState


class FollowUpQuery(BaseModel):
    """A search that would fill a gap in the research."""
    subtopic: str = Field(description="An existing subtopic title copied exactly, or a short new title for a missing angle")
    query: str = Field(description="Self-contained web search query")


class Critique(BaseModel):
    """Assessment of whether the research answers the topic."""
    critique: str = Field(description="One or two sentences on the main strengths and gaps")
    is_complete: bool = Field(description="True if the summary answers the topic comprehensively")
    follow_up_queries: List[FollowUpQuery] = Field(description="Searches that would fill the most important gaps; empty when complete")


def _format_summary_for_critique(state: ResearchState) -> str:
    text = ""
    for subtopic in state.subtopics:
        bullets = state.bullets.get(subtopic, [])
        text += f"Subtopic: {subtopic}\n"
        text += "\n".join(f"- {bullet.text}" for bullet in bullets) or "- (no findings: no relevant sources were found)"
        text += "\n\n"
    return text.strip()

def _queue_follow_ups(state: ResearchState, follow_ups: List[FollowUpQuery]) -> tuple[List[str], dict[str, List[str]]]:
    """Attach follow-up queries to their subtopics, adding new subtopics up to MAX_TOTAL_SUBTOPICS."""
    subtopics = list(state.subtopics)
    by_name = {subtopic.lower(): subtopic for subtopic in subtopics}
    pending = {}
    for item in follow_ups[:MAX_FOLLOW_UP_QUERIES]:
        title = " ".join(item.subtopic.split())
        query = " ".join(item.query.split())
        if not title or not query:
            continue
        subtopic = by_name.get(title.lower())
        if subtopic is None:
            if len(subtopics) >= MAX_TOTAL_SUBTOPICS:
                print(f"[!] Skipped follow-up for new subtopic '{title}': subtopic limit reached")
                continue
            subtopic = by_name[title.lower()] = title
            subtopics.append(subtopic)
        pending.setdefault(subtopic, []).append(query)
    return subtopics, pending

def _queue_gap_searches(state: ResearchState, pending: dict[str, List[str]]) -> int:
    """Re-search every subtopic that still has no findings and no follow-up query: the critic often
    calls the research incomplete without suggesting searches for exactly these gaps."""
    gaps = [subtopic for subtopic in state.subtopics if not state.bullets.get(subtopic) and subtopic not in pending]
    for subtopic in gaps:
        # Worded differently from the planner's query; URLs the subtopic has already seen are skipped anyway
        pending[subtopic] = [f"{subtopic} {state.topic}"]
    return len(gaps)

async def critiquer_fn(state: ResearchState) -> dict:
    """Evaluate the generated summary and queue follow-up searches if revision is needed."""
    revision_number = state.revision_number + 1
    prompt = critique_prompt.invoke({
        "topic": state.topic,
        "subtopics": escape_untrusted("\n".join(f"- {subtopic}" for subtopic in state.subtopics)),
        "summary_text": escape_untrusted(_format_summary_for_critique(state)),
        "max_follow_ups": MAX_FOLLOW_UP_QUERIES,
    })
    result = await invoke_structured(LLM_CRITIQUER, Critique, prompt, "critique")

    update = {"critique": result.critique if result else None, "needs_revision": False, "revision_number": revision_number}
    if result is None:
        verdict = "critique unavailable"
    else:
        verdict = "complete" if result.is_complete else "incomplete"

    if revision_number >= state.max_revisions:
        decision = "Complete" if verdict == "complete" else f"Finalizing ({verdict}, no revisions left)"
    else:
        # Only queue searches when the graph will run them, so no subtopic is left without a search
        follow_ups = result.follow_up_queries if result and not result.is_complete else []
        subtopics, pending = _queue_follow_ups(state, follow_ups)
        follow_up_count = sum(len(queries) for queries in pending.values())
        gap_count = _queue_gap_searches(state, pending)
        if pending:
            update.update(subtopics=subtopics, pending_queries=pending, needs_revision=True)
            decision = f"Revision Needed ({verdict}: {follow_up_count} follow-up searches, {gap_count} subtopics without findings re-searched)"
        else:
            decision = "Complete" if verdict == "complete" else f"Finalizing ({verdict}, nothing left to search)"

    print(f"--- Critique ---\nCritique: {update['critique']}\nDecision: {decision}\n--------------\n")
    return update

CritiquerAgent = RunnableLambda(critiquer_fn)
