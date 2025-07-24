import ast
from typing import Optional
from langchain_core.runnables import RunnableLambda
from config import LLM_PLANNER
from tools.prompts import planner_prompt
from graph.state import ResearchState # Import ResearchState for type hinting

def _parse_planner_response(response_content: str) -> Optional[list[str]]:
    try:
        if "```python" in response_content:
            code_block = response_content.split("```python\n")[1].split("```")[0]
            return ast.literal_eval(code_block)
        return ast.literal_eval(response_content)
    except (SyntaxError, ValueError, IndexError):
        print(f"[!] Failed to parse planner response: {response_content}")
        return None

async def planner_fn(state: ResearchState) -> dict: # Use ResearchState type hint
    """Given a topic, invoke the planner LLM to get subtopics."""
    prompt = planner_prompt.invoke({"topic": state.topic}) # Use state.topic
    response = await LLM_PLANNER.ainvoke(prompt)
    subtopics = _parse_planner_response(response.content)

    if not subtopics:
        return {"subtopics": []}

    print(f"--- Subtopics Generated ---\n{subtopics}\n")
    return {"subtopics": subtopics}

PlannerAgent = RunnableLambda(planner_fn)