import os
from datetime import date
from typing import Optional
from urllib.parse import urlparse
from tavily import AsyncTavilyClient
from tavily.errors import ForbiddenError, InvalidAPIKeyError, MissingAPIKeyError
from config import MAX_SEARCH_RESULTS, MAX_CHARS_PER_DOCUMENT, EXCLUDED_DOMAINS, DATE_FILTER_MAX_YEARS_AGO, MIN_SEARCH_SCORE
from graph.state import SearchResult
from tools.errors import ServiceError
from tools.time_frame import topic_year

_client: Optional[AsyncTavilyClient] = None


def _get_client() -> AsyncTavilyClient:
    # Created on first use, so importing this module doesn't require TAVILY_API_KEY
    global _client
    if _client is None:
        _client = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    return _client


def search_date_range(topic: str, today: Optional[date] = None) -> tuple[Optional[str], Optional[str]]:
    """For a topic about one recent year ("... in 2025"), return the publish-date window to search:
    that year plus the next three months, when year-end reviews appear. Otherwise (None, None).
    (A longer window lets in next year's unrelated events.)"""
    today = today or date.today()
    year = topic_year(topic)
    if year is None or not today.year - DATE_FILTER_MAX_YEARS_AGO <= year <= today.year:
        return None, None
    return date(year, 1, 1).isoformat(), min(date(year + 1, 3, 31), today).isoformat()


def _is_excluded(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == domain or host.endswith("." + domain) for domain in EXCLUDED_DOMAINS)


async def search_web(query: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> list[SearchResult]:
    """Search the web for a query. Returns [] on one-off errors."""
    try:
        results = await _get_client().search(
            query=query,
            max_results=MAX_SEARCH_RESULTS,
            exclude_domains=EXCLUDED_DOMAINS,
            start_date=start_date,
            end_date=end_date,
            # Tavily's own copy of each page: the fallback when a site blocks our fetch, and the only way to read PDFs
            include_raw_content="text",
        )
    except (InvalidAPIKeyError, ForbiddenError, MissingAPIKeyError) as e:
        # A rejected key or an exhausted plan fails every search, so stop instead of researching nothing
        raise ServiceError(f"Tavily rejected the search ({type(e).__name__}): {e}") from e
    except Exception as e:
        print(f"Error during web search for '{query}': {e}")
        return []

    items = [item for item in results.get("results", []) if item.get("url") and not _is_excluded(item["url"])]
    # Low-scoring hits are mostly keyword matches (fund reports, tax forms); skipping them saves a summary call each
    relevant = [item for item in items if item.get("score") is None or item["score"] >= MIN_SEARCH_SCORE]
    if len(relevant) < len(items):
        print(f"[~] Skipped {len(items) - len(relevant)} low-relevance results for '{query}'")
    return [
        SearchResult(
            title=" ".join((item.get("title") or "").split()),
            # URL fragments never reach the server, so dropping them dedupes the same page
            url=item["url"].split("#", 1)[0],
            content=(item.get("raw_content") or "")[:MAX_CHARS_PER_DOCUMENT],
        )
        for item in relevant
    ]
