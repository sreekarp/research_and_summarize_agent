import os

# Fake keys before anything imports config (which builds the Groq clients). load_dotenv() never overrides
# a variable that is already set, so a real .env in the repo can't turn a test into a live API call.
os.environ["GROQ_API_KEY"] = "test-groq-key"
os.environ["TAVILY_API_KEY"] = "test-tavily-key"

import pytest  # noqa: E402

import tools.web_loader as web_loader  # noqa: E402
from tools import llm, search_api  # noqa: E402
from fakes import FAKE_DNS  # noqa: E402

REAL_RESOLVE = web_loader._resolve


async def fake_resolve(host, port):
    if host not in FAKE_DNS:
        raise OSError(f"no such host: {host}")
    return FAKE_DNS[host]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """No test resolves real hostnames, and module state from one test (failure count, a Tavily client
    bound to an earlier event loop) never leaks into the next."""
    monkeypatch.setattr(web_loader, "_resolve", fake_resolve)
    monkeypatch.setattr(llm, "failed_calls", 0)
    monkeypatch.setattr(search_api, "_client", None)
