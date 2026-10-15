import asyncio
import ipaddress
import socket
import zlib
from typing import Optional
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from config import (
    MAX_CHARS_PER_DOCUMENT, MAX_DOWNLOAD_BYTES, MAX_REDIRECTS, FETCH_TIMEOUT_SECONDS, FETCH_DEADLINE_SECONDS,
)

# Only gzip is accepted, so the download cap can be applied to the decompressed size (see _read_body)
# Sites like Wikipedia refuse clients whose User-Agent has no contact URL
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; research-and-summarize-agent/1.0; +https://github.com/sreekarp/research_and_summarize_agent)",
    "Accept-Encoding": "gzip",
}
ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
STRIPPED_TAGS = ["script", "style", "noscript", "template", "nav", "footer", "aside", "svg", "iframe", "button", "select", "textarea"]


class FetchError(Exception):
    pass


async def _resolve(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos]


def _is_public_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global


async def check_url(url: str) -> Optional[str]:
    """Return why a URL must not be fetched, or None if it is a public http(s) URL.

    The host is resolved first, so names that point at localhost or private networks are blocked too.
    (A DNS server that answers differently on the second lookup could still get through.)"""
    try:
        parsed = urlparse(url)
        host, port = parsed.hostname, parsed.port
    except ValueError:
        return "malformed URL"
    if parsed.scheme not in ("http", "https") or not host:
        return "not an http(s) URL"
    try:
        addresses = await _resolve(host, port or (443 if parsed.scheme == "https" else 80))
    except (OSError, UnicodeError):
        return "host could not be resolved"
    if not addresses or not all(_is_public_ip(address) for address in addresses):
        return "blocked non-public address"
    return None


def create_http_client() -> httpx.AsyncClient:
    """One shared client per retrieval pass, so pages reuse connections.
    Redirects are followed by load_url_text, so every hop gets checked."""
    return httpx.AsyncClient(follow_redirects=False, timeout=FETCH_TIMEOUT_SECONDS, headers=HEADERS)


async def _read_body(response: httpx.Response) -> bytes:
    """Read at most MAX_DOWNLOAD_BYTES of decoded content, decompressing gzip ourselves so a
    small compressed body can't expand into gigabytes before the cap applies."""
    content_encoding = response.headers.get("content-encoding", "").strip().lower()
    if content_encoding not in ("", "identity", "gzip"):
        raise FetchError(f"unsupported content encoding '{content_encoding}'")
    decoder = zlib.decompressobj(wbits=31) if content_encoding == "gzip" else None

    body = bytearray()
    async for chunk in response.aiter_raw():
        body.extend(decoder.decompress(chunk, MAX_DOWNLOAD_BYTES - len(body)) if decoder else chunk)
        if len(body) >= MAX_DOWNLOAD_BYTES:
            break
    return bytes(body[:MAX_DOWNLOAD_BYTES])


def _extract_text(body: bytes, encoding: Optional[str]) -> str:
    soup = BeautifulSoup(body, "html.parser", from_encoding=encoding)
    for tag in soup(STRIPPED_TAGS):
        tag.decompose()
    # Site banners are noise, but a <header> inside an article holds its headline and date
    for header in soup.find_all("header"):
        if not header.decomposed and not header.find_parent(["article", "main"]):
            header.decompose()
    return "\n".join(soup.stripped_strings)


async def _fetch_text(client: httpx.AsyncClient, url: str) -> str:
    for _ in range(MAX_REDIRECTS + 1):
        problem = await check_url(url)
        if problem:
            raise FetchError(problem)
        async with client.stream("GET", url) as response:
            if response.is_redirect:
                url = str(response.url.join(response.headers["location"]))
                continue
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type and content_type not in ALLOWED_CONTENT_TYPES:
                raise FetchError(f"unsupported content type '{content_type}'")
            body = await _read_body(response)
            return _extract_text(body, response.charset_encoding)
    raise FetchError(f"more than {MAX_REDIRECTS} redirects")


async def load_url_text(client: httpx.AsyncClient, url: str) -> str:
    """Asynchronously load and extract main body text from a URL. Returns "" for pages that can't be used."""
    try:
        text = await asyncio.wait_for(_fetch_text(client, url), FETCH_DEADLINE_SECONDS)
        return text[:MAX_CHARS_PER_DOCUMENT]
    except (httpx.HTTPError, httpx.StreamError, FetchError) as e:
        print(f"Error loading URL {url}: {e}")
        return ""
    except asyncio.TimeoutError:
        print(f"Error loading URL {url}: no complete response within {FETCH_DEADLINE_SECONDS}s")
        return ""
    except Exception as e:
        print(f"An unexpected error occurred for URL {url}: {e}")
        return ""
