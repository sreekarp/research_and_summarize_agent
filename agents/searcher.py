import asyncio
from langchain_core.runnables import RunnableLambda
from tools.search_api import search_web
from graph.state import ResearchState

async def searcher_fn(state: ResearchState) -> dict:
    """For each subtopic, perform a web search in parallel."""
    subtopics = state.subtopics # Use state.subtopics
    
    search_tasks = [search_web(subtopic) for subtopic in subtopics]
    search_results_list = await asyncio.gather(*search_tasks)
    
    results = {subtopic: res for subtopic, res in zip(subtopics, search_results_list)}
    
    print("--- Search Results ---")
    for subtopic, links in results.items():
        print(f"[{subtopic}] Found {len(links)} links.")
    print("----------------------\n")
    
    return {"search_results": results}

SearcherAgent = RunnableLambda(searcher_fn)