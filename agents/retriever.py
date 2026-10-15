import asyncio
from langchain_core.runnables import RunnableLambda
from tools.web_loader import create_http_client, load_url_text
from config import MIN_WORDS_PER_DOCUMENT
from graph.state import ResearchState, SearchResult, Document


def _has_content(text: str) -> bool:
    return len(text.split()) >= MIN_WORDS_PER_DOCUMENT

async def _load_page(client, result: SearchResult) -> str:
    """Fetch a page ourselves; if the site blocks us or it isn't HTML (e.g. a PDF), use the search engine's copy."""
    url = result.url
    print(f"--- Retrieving: {url} ---")
    text = await load_url_text(client, url)
    if _has_content(text):
        return text
    if _has_content(result.content):
        print(f"[~] Using the search engine's copy of {url}")
        return result.content
    print(f"[!] No meaningful content at {url}")
    return ""

async def retriever_fn(state: ResearchState) -> dict:
    """Fetch the new search results in parallel and add them to the documents, numbered for citation.
    Relevance is judged later, by the summarizer, on the whole page."""
    jobs = [(subtopic, result) for subtopic, results in state.search_results.items() for result in results]

    # Each page is fetched once per pass even when several subtopics found it; pages kept earlier aren't refetched
    texts = {doc.url: doc.text for docs in state.documents.values() for doc in docs}
    to_fetch = list({result.url: result for _, result in jobs if result.url not in texts}.values())
    async with create_http_client() as client:
        pages = await asyncio.gather(*(_load_page(client, result) for result in to_fetch))
    texts.update((result.url, text) for result, text in zip(to_fetch, pages))

    # Documents accumulate across passes; ids continue from the last pass so citations stay unique
    documents = {subtopic: list(state.documents.get(subtopic, [])) for subtopic in state.subtopics}
    next_id = 1 + max((doc.id for docs in state.documents.values() for doc in docs), default=0)
    for subtopic, result in jobs:
        if texts.get(result.url):
            documents.setdefault(subtopic, []).append(Document(id=next_id, url=result.url, title=result.title, text=texts[result.url]))
            next_id += 1

    print("\n--- Retrieval Complete ---")
    for subtopic, docs in documents.items():
        print(f"[{subtopic}] Retrieved {len(docs)} documents.")
    print("------------------------\n")

    return {"documents": documents}

RetrieverAgent = RunnableLambda(retriever_fn)
