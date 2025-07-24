from langchain_core.runnables import RunnableLambda
from config import LLM_CRITIQUER
from tools.prompts import critique_prompt
from graph.state import ResearchState

def _format_summary_for_critique(bullets: dict) -> str:
    text = ""
    for subtopic, points in bullets.items():
        text += f"Subtopic: {subtopic}\n"
        text += "\n".join(points) + "\n\n"
    return text.strip()

async def critiquer_fn(state: ResearchState) -> dict:
    """Evaluate the generated summary and decide if revision is needed."""
    summary_text = _format_summary_for_critique(state.bullets) # Use state.bullets
    
    prompt = critique_prompt.invoke({
        "topic": state.topic, # Use state.topic
        "summary_text": summary_text
    })
    response = await LLM_CRITIQUER.ainvoke(prompt)
    
    lines = response.content.strip().split("\n")
    critique = lines[0]
    decision = lines[-1].lower()
    
    needs_revision = "incomplete" in decision
    
    print(f"--- Critique ---\nCritique: {critique}\nDecision: {'Revision Needed' if needs_revision else 'Complete'}\n--------------\n")

    return {"critique": critique, "needs_revision": needs_revision}

CritiquerAgent = RunnableLambda(critiquer_fn)