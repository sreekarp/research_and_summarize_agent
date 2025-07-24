import httpx
from bs4 import BeautifulSoup
from config import MAX_CHARS_PER_DOCUMENT

async def load_url_text(url: str) -> str:
    """Asynchronously load and extract main body text from a URL."""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status() # Raise an exception for bad status codes

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "aside"]):
            tag.decompose()
        
        text = "\n".join(t.strip() for t in soup.stripped_strings)
        return text[:MAX_CHARS_PER_DOCUMENT]
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        print(f"Error loading URL {url}: {e}")
        return ""
    except Exception as e:
        print(f"An unexpected error occurred for URL {url}: {e}")
        return ""