import asyncio
from langchain_core.runnables import RunnableLambda
from config import LLM_SUMMARIZER
from tools.prompts import map_summarize_prompt, reduce_bullets_prompt
from graph.state import ResearchState

async def _map_summarize_doc(document: dict, subtopic: str) -> str:
    prompt = map_summarize_prompt.invoke({
        "subtopic": subtopic,
        "text": document["text"]
    })
    response = await LLM_SUMMARIZER.ainvoke(prompt)
    return response.content

async def summarizer_fn(state: ResearchState) -> dict:
    """Summarize content for each subtopic using a map-reduce approach."""
    bullets_by_topic = {}
    documents_by_topic = state.documents # Use state.documents

    for subtopic, docs in documents_by_topic.items():
        if not docs:
            bullets_by_topic[subtopic] = []
            continue

        map_tasks = [_map_summarize_doc(doc, subtopic) for doc in docs]
        individual_summaries = await asyncio.gather(*map_tasks)
        
        combined_summary = "\n\n".join(individual_summaries)
        reduce_prompt = reduce_bullets_prompt.invoke({
            "subtopic": subtopic,
            "summaries": combined_summary
        })
        final_summary_resp = await LLM_SUMMARIZER.ainvoke(reduce_prompt)
        
        bullets = [b.strip() for b in final_summary_resp.content.strip().split("\n") if b.strip()]
        bullets_by_topic[subtopic] = bullets

    print("\n--- Summarization Complete ---")
    for subtopic, bullets in bullets_by_topic.items():
        print(f"[{subtopic}] Generated {len(bullets)} bullet points.")
    print("--------------------------\n")

    return {"bullets": bullets_by_topic}

SummarizerAgent = RunnableLambda(summarizer_fn)