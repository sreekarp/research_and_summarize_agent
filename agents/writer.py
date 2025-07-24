from langchain_core.runnables import RunnableLambda
from config import LLM_WRITER
from tools.prompts import writer_prompt
from graph.state import ResearchState

def _format_summary_for_writer(bullets: dict) -> str:
    text = ""
    for subtopic, points in bullets.items():
        text += f"## {subtopic}\n\n"
        text += "\n".join(f"* {point}" for point in points) + "\n\n"
    return text.strip()

async def writer_fn(state: ResearchState) -> dict:
    """Generate the final markdown report from the bullet points."""
    summary_text = _format_summary_for_writer(state.bullets) # Use state.bullets
    
    prompt = writer_prompt.invoke({
        "topic": state.topic, # Use state.topic
        "summary_text": summary_text
    })
    
    response = await LLM_WRITER.ainvoke(prompt)
    
    print("--- Final Report Generated ---\n")
    return {"report": response.content}

WriterAgent = RunnableLambda(writer_fn)