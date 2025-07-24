import os
import asyncio
from tavily import TavilyClient
from config import MAX_SEARCH_RESULTS

client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

async def search_web(query: str) -> list[dict]:
    """Asynchronously search the web for a query using asyncio.to_thread."""
    try:
        # Run the synchronous search client in a separate thread
        results = await asyncio.to_thread(
            client.search,
            query=query,
            max_results=MAX_SEARCH_RESULTS
        )
        return [
            {"title": item.get("title"), "href": item.get("url")}
            for item in results.get("results", [])
        ]
    except Exception as e:
        print(f"Error during web search for '{query}': {e}")
        return []