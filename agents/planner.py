from typing import List
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableLambda
from config import LLM_PLANNER, MAX_SUBTOPICS
from tools.llm import invoke_structured
from tools.prompts import planner_prompt
from graph.state import ResearchState


class PlannedSubtopic(BaseModel):
    """One subtopic of the research plan."""
    title: str = Field(description="Short section heading for the subtopic")
    query: str = Field(description="Self-contained web search query that includes the main topic")


class ResearchPlan(BaseModel):
    """Distinct subtopics that together cover the topic."""
    subtopics: List[PlannedSubtopic] = Field(description="3-5 distinct subtopics")


def _clean_plan(plan: ResearchPlan) -> dict[str, str]:
    """Drop blank and duplicate subtopics and keep at most MAX_SUBTOPICS. Returns {title: search query}."""
    cleaned = {}
    for item in plan.subtopics:
        title = " ".join(item.title.split())
        query = " ".join(item.query.split()) or title
        if not title or title.lower() in (t.lower() for t in cleaned):
            continue
        cleaned[title] = query
        if len(cleaned) == MAX_SUBTOPICS:
            break
    return cleaned


async def planner_fn(state: ResearchState) -> dict:
    """Given a topic, invoke the planner LLM to get subtopics and a search query for each."""
    prompt = planner_prompt.invoke({"topic": state.topic})
    plan = await invoke_structured(LLM_PLANNER, ResearchPlan, prompt, "planner")
    queries = _clean_plan(plan) if plan else {}

    if not queries:
        print("[!] Planner produced no usable subtopics")
        return {"subtopics": []}

    print(f"--- Subtopics Generated ---\n{list(queries)}\n")
    return {
        "subtopics": list(queries),
        "pending_queries": {title: [query] for title, query in queries.items()},
    }

PlannerAgent = RunnableLambda(planner_fn)
