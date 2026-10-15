"""Fake Groq, Tavily and web servers for offline tests.

The real ChatGroq, AsyncTavilyClient and httpx clients run unchanged; respx intercepts their HTTP requests
and these handlers answer them. Override a method in a subclass to script a scenario."""
import contextlib
import io
import json
import re
from collections import Counter

import httpx
import respx

FAKE_DNS = {
    "ex.com": ["93.184.216.34"],
    "internal.ex.com": ["10.0.0.5"],
    "localhost": ["127.0.0.1"],
    "localhost.": ["127.0.0.1"],
    "mapped.ex.com": ["::ffff:127.0.0.1"],
    "127.0.0.1": ["127.0.0.1"],
}

WORDS = " ".join(f"word{i}" for i in range(80))  # enough text to pass MIN_WORDS_PER_DOCUMENT
BAD_REQUEST = object()  # return from a handler to make that call fail with a one-off 400
NO_RETRY = {"x-should-retry": "false"}  # makes the Groq client give up on a 429 at once
HTML = {"content-type": "text/html; charset=utf-8"}


def page(marker: str, extra: str = "") -> str:
    return (f"<html><head><title>{marker}</title></head><body><header>SITE BANNER</header><nav>menu links</nav>"
            f"<article><header>HEADLINE 2024-05-01</header><p>{marker} {extra} {WORDS}</p></article>"
            f"<script>evil()</script></body></html>")


def completion(content: str) -> dict:
    return {"id": "x", "object": "chat.completion", "created": 0, "model": "openai/gpt-oss-120b",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}


class FakeServices:
    """A topic about solar power with three planned subtopics, one critic revision, and pages that exercise
    every fetch guardrail (a PDF, a blocked localhost link, a redirect to an internal IP, a social-media link)."""

    SEARCH = {
        "solar power cost trends": ["https://ex.com/cost1", "https://ex.com/cost2#section", "https://ex.com/report.pdf",
                                    "http://localhost/admin", "http://internal.ex.com/x", "https://m.facebook.com/videos/123"],
        "solar power grid integration": ["https://ex.com/grid1", "https://ex.com/cost1", "https://ex.com/redirect"],
        "solar power policy": ["https://ex.com/policy-irrelevant", "https://ex.com/short"],
        "solar subsidies by country": ["https://ex.com/policy2", "https://ex.com/cost1"],
        "solar panel environmental impact": ["https://ex.com/env1"],
        "solar cost outlook": ["https://ex.com/cost3"],
        "Policy Solar power": ["https://ex.com/policy-gap"],
    }
    # Tavily's own copy of a page (include_raw_content): the PDF can only be read this way
    RAW = {"https://ex.com/report.pdf": f"MARKER_pdf {WORDS}"}

    def __init__(self):
        self.llm_calls = Counter()
        self.prompts = []  # (schema name or "writer", prompt text)
        self.fetches = Counter()
        self.tavily_requests = []
        self.user_agents = set()
        self.critiques = 0
        self.strict_ok = True

    # --- scenario behaviour ---------------------------------------------------------------------
    def plan(self):
        return {"subtopics": [
            {"title": "Cost trends", "query": "solar power cost trends"},
            {"title": "  cost   TRENDS ", "query": "dup"},
            {"title": "   ", "query": "blank"},
            {"title": "Grid integration", "query": "solar power grid integration"},
            {"title": "Policy", "query": "solar power policy"},
        ]}

    def relevant(self, prompt):
        return "IRRELEVANT" not in prompt

    def page_summary(self, prompt):
        if not self.relevant(prompt):
            return {"relevant": False, "summary": ""}
        marker = re.search(r"MARKER_\w+", prompt)
        return {"relevant": True, "summary": f"Key facts from {marker.group(0) if marker else 'page'}."}

    def bullets(self, prompt):
        ids = [int(i) for i in re.findall(r'<source id="(\d+)">', prompt)]
        return {"bullets": [
            {"text": "- Fact A [1]", "source_ids": [ids[0]]},
            {"text": "Fact B about everything", "source_ids": ids + [999]},
            {"text": "Uncited fact", "source_ids": [999]},
        ]}

    def follow_ups(self):
        return [
            {"subtopic": "policy", "query": "solar subsidies by country"},
            {"subtopic": "Environmental impact", "query": "solar panel environmental impact"},
            {"subtopic": "Grid integration", "query": "solar power grid integration"},
        ]

    def critique(self):
        self.critiques += 1
        if self.critiques == 1:
            return {"critique": "Missing environmental angle.", "is_complete": False, "follow_up_queries": self.follow_ups()}
        return {"critique": "Good coverage.", "is_complete": True, "follow_up_queries": []}

    def writer(self, prompt):
        return ("```markdown\n# Solar Report\n\nIntro [1] and bogus [99] and combo [1, 99].\n\n"
                "## Policy\n\nPolicy text [2].\n\n## References\n\n1. fake ref - <http://made.up>\n```")

    def search(self, query):
        return [{"title": f"Title of {url.rsplit('/', 1)[-1]}", "url": url, "content": "", "raw_content": self.RAW.get(url), "score": 0.9}
                for url in self.SEARCH.get(query, [])]

    # --- HTTP handlers ----------------------------------------------------------------------------
    def groq(self, request):
        body = json.loads(request.content)
        prompt = body["messages"][-1]["content"]
        response_format = body.get("response_format")
        if response_format:
            name = response_format["json_schema"]["name"]
            self.strict_ok &= response_format["type"] == "json_schema" and response_format["json_schema"].get("strict") is True
            self.llm_calls[name] += 1
            self.prompts.append((name, prompt))
            content = {"ResearchPlan": self.plan, "PageSummary": lambda: self.page_summary(prompt),
                       "BulletList": lambda: self.bullets(prompt), "Critique": self.critique}[name]()
            if isinstance(content, httpx.Response):
                return content
            if content is not BAD_REQUEST:
                content = json.dumps(content)
        else:
            self.llm_calls["writer"] += 1
            self.prompts.append(("writer", prompt))
            content = self.writer(prompt)
        if content is BAD_REQUEST:
            return httpx.Response(400, json={"error": {"message": "bad request", "type": "invalid_request_error"}})
        return httpx.Response(200, json=completion(content))

    def tavily(self, request):
        body = json.loads(request.content)
        self.tavily_requests.append(body)
        return httpx.Response(200, json={"query": body["query"], "results": self.search(body["query"]), "response_time": 0.1})

    def web(self, request):
        url = str(request.url)
        self.fetches[url] += 1
        self.user_agents.add(request.headers.get("user-agent", ""))
        name = url.rsplit("/", 1)[-1]
        if name == "report.pdf":
            return httpx.Response(200, content=b"%PDF-1.4 binary", headers={"content-type": "application/pdf"})
        if name == "redirect":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
        if name == "short":
            return httpx.Response(200, text="<html><body>too short</body></html>", headers=HTML)
        if "irrelevant" in name:
            return httpx.Response(200, text=page(f"MARKER_{name.replace('-', '_')}", "IRRELEVANT"), headers=HTML)
        return httpx.Response(200, text=page(f"MARKER_{name}"), headers=HTML)

    def prompts_for(self, name):
        return [prompt for kind, prompt in self.prompts if kind == name]


@contextlib.contextmanager
def mocked_network(services: FakeServices):
    """Route Groq, Tavily and page requests to `services`; any other request fails the test."""
    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://api.groq.com/openai/v1/chat/completions").mock(side_effect=services.groq)
        mock.post("https://api.tavily.com/search").mock(side_effect=services.tavily)
        mock.get(url__regex=r"^https?://(ex\.com|internal\.ex\.com|localhost|127\.0\.0\.1)(/.*)?$").mock(side_effect=services.web)
        yield mock


async def run_pipeline(services: FakeServices, topic: str = "Solar power"):
    """Run main.main() against the fakes. Returns (exit code, stdout, stderr, extracted report)."""
    import main
    out, err = io.StringIO(), io.StringIO()
    with mocked_network(services), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = await main.main(topic)
    log = out.getvalue()
    match = re.search(r"FINAL RESEARCH REPORT\n=+\n\n(.*?)=== Research Complete", log, re.DOTALL)
    return code, log, err.getvalue(), match.group(1).strip() if match else ""
