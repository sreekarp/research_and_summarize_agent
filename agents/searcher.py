import asyncio
from langchain_core.runnables import RunnableLambda
from tools.search_api import search_web, search_date_range
from graph.state import ResearchState

async def searcher_fn(state: ResearchState) -> dict:
    """Run the queued search queries in parallel, keeping only URLs an earlier pass hasn't seen for that subtopic."""
    start_date, end_date = search_date_range(state.topic)
    if start_date:
        print(f"--- Limiting searches to pages published {start_date} to {end_date} ---")

    jobs = [(subtopic, query) for subtopic, queries in state.pending_queries.items() for query in queries]
    for subtopic, query in jobs:
        print(f"--- Searching [{subtopic}]: {query} ---")
    responses = await asyncio.gather(*(search_web(query, start_date, end_date) for _, query in jobs))

    seen_urls = {subtopic: list(urls) for subtopic, urls in state.seen_urls.items()}
    results = {}
    for (subtopic, _), hits in zip(jobs, responses, strict=True):
        seen = seen_urls.setdefault(subtopic, [])
        new_hits = results.setdefault(subtopic, [])
        for hit in hits:
            if hit.url not in seen:
                seen.append(hit.url)
                new_hits.append(hit)

    print("--- Search Results ---")
    for subtopic, links in results.items():
        print(f"[{subtopic}] Found {len(links)} new links.")
    print("----------------------\n")

    return {"search_results": results, "seen_urls": seen_urls, "pending_queries": {}}

SearcherAgent = RunnableLambda(searcher_fn)
