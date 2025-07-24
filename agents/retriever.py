import asyncio
from typing import Optional
from langchain_core.runnables import RunnableLambda
from tools.web_loader import load_url_text
from tools.prompts import relevance_check_prompt
from config import LLM_PLANNER
from graph.state import ResearchState

async def _filter_and_load_link(link: dict, subtopic: str) -> Optional[dict]:
    url = link.get("href")
    if not url:
        return None

    print(f"--- Retrieving: {url} ---")
    text = await load_url_text(url)

    if not text or len(text.split()) < 50:
        print(f"[!] No meaningful content at {url}")
        return None

    prompt = relevance_check_prompt.invoke({"subtopic": subtopic, "text": text[:500]})
    response = await LLM_PLANNER.ainvoke(prompt)

    if "irrelevant" in response.content.lower():
        print(f"[!] Discarded as irrelevant: {url}")
        return None

    print(f"[+] Kept as relevant: {url}")
    return {"text": text, "source": url}

async def retriever_fn(state: ResearchState) -> dict:
    """For each subtopic, retrieve and filter content from URLs in parallel."""
    results = {}
    search_results = state.search_results # Use state.search_results

    for subtopic, links in search_results.items():
        tasks = [_filter_and_load_link(link, subtopic) for link in links]
        retrieved_docs = await asyncio.gather(*tasks)
        results[subtopic] = [doc for doc in retrieved_docs if doc]

    print("\n--- Retrieval Complete ---")
    for subtopic, docs in results.items():
        print(f"[{subtopic}] Retrieved {len(docs)} relevant documents.")
    print("------------------------\n")

    return {"documents": results}

RetrieverAgent = RunnableLambda(retriever_fn)