import asyncio
from datetime import date

import groq
import httpx
import pytest

from tools import llm
from tools.search_api import _is_excluded, search_date_range
from tools.time_frame import topic_year

TODAY = date(2026, 10, 15)


@pytest.mark.parametrize("topic, window", [
    ("India in 2025", ("2025-01-01", "2026-03-31")),
    ("elections during 2026", ("2026-01-01", "2026-10-15")),  # current year: clamped to today
    ("the financial crisis of 2008", (None, None)),
    ("growth since 2024", (None, None)),
    ("plans for 2030", (None, None)),  # future year
    ("in 2024 and in 2025", (None, None)),  # two years
    ("AI in 2007", (None, None)),  # older years: look-back analyses written later matter
])
def test_search_date_range(topic, window):
    assert search_date_range(topic, TODAY) == window


def test_topic_year():
    assert topic_year("India in 2025") == 2025
    assert topic_year("solar power") is None


@pytest.mark.parametrize("url, excluded", [
    ("https://m.facebook.com/v", True), ("https://x.com/a", True), ("https://www.youtube.com/watch", True),
    ("https://notfacebook.com/", False), ("https://box.com/", False),
])
def test_excluded_domains_match_subdomains_only(url, excluded):
    assert _is_excluded(url) == excluded


def _status_error(cls, status, body):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return cls(str(body), response=httpx.Response(status, request=request, json=body), body=body)


@pytest.mark.parametrize("error, fatal", [
    (_status_error(groq.AuthenticationError, 401, {"error": {"code": "invalid_api_key"}}), True),
    (_status_error(groq.NotFoundError, 404, {"error": {"code": "model_not_found"}}), True),
    (_status_error(groq.BadRequestError, 400, {"error": {"code": "model_decommissioned"}}), True),
    (_status_error(groq.BadRequestError, 400, {"error": {"code": "json_validate_failed"}}), False),
    (_status_error(groq.RateLimitError, 429, {"error": {"message": "Rate limit reached on tokens per day (TPD)"}}), True),
    (_status_error(groq.RateLimitError, 429, {"error": {"message": "Rate limit reached on tokens per minute (TPM)"}}), False),
    (ValueError("anything else"), False),
])
def test_fatal_error_classification(error, fatal):
    assert llm._is_fatal(error) == fatal


def test_semaphore_works_across_event_loops():
    # An asyncio.Semaphore made at import time would fail in the second loop; tools/llm.py keeps one per loop
    class Slow:
        async def ainvoke(self, prompt):
            await asyncio.sleep(0.01)
            return type("Reply", (), {"content": "ok"})()

    async def burst():
        return await asyncio.gather(*(llm.invoke_text(Slow(), "p", "probe") for _ in range(5)))

    for _ in range(2):
        loop = asyncio.new_event_loop()
        try:
            assert loop.run_until_complete(burst()) == ["ok"] * 5
        finally:
            loop.close()
