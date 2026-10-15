# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
python -m venv venv && source venv/bin/activate   # Python 3.10+ (LangGraph requires it); on Windows: venv\Scripts\activate
pip install -r requirements-dev.txt     # pinned app dependencies + pytest/respx/ruff
python main.py "Some research topic"   # defaults to "Impact of generative AI on education"
ruff check .                           # lint (bug-focused rules, see pyproject.toml)
pytest                                 # offline test suite, ~1 minute
pytest tests/test_pipeline.py -k gap   # a single test
```

Requires a `.env` in the repo root with `TAVILY_API_KEY` and `GROQ_API_KEY` (`.env` is gitignored); `main.py` exits with code 2 and a clear message if either is missing. Exit code 1 means no report was produced (planner returned nothing, nothing could be cited, or a `ServiceError` stopped the run). Dependencies are pinned with `==` in `requirements.txt`; bump them deliberately and rerun the tests. CI (`.github/workflows/ci.yml`) runs ruff and pytest on Python 3.10 and 3.12.

## Tests

The tests never call real APIs. `tests/fakes.py` has `FakeServices`, which answers Groq, Tavily and page requests through respx while the real clients and graph run unchanged; `tests/conftest.py` sets fake API keys before anything imports `config` and fakes DNS for every test. To script a scenario, subclass `FakeServices`, override a method (`plan`, `relevant`, `page_summary`, `bullets`, `follow_ups`, `critique`, `writer`, `search`, `tavily`), and call `run_pipeline()`. Return `BAD_REQUEST` or an `httpx.Response` from a handler to simulate failures. Tests that run `main.py` as a subprocess must keep API keys empty (not absent), or the real `.env` would be loaded and make live calls.

## Architecture

A LangGraph `StateGraph` pipeline of LLM "agents" that researches a topic and prints a Markdown report with numbered citations.

**Flow** (`graph/graph_builder.py`):
`planner → searcher → retriever → summarizer → critiquer → (searcher again | writer) → END`.
If the planner produces no subtopics, the graph ends immediately.

**State** (`graph/state.py`): a single Pydantic `ResearchState`. Each stage reads earlier fields and fills its own, mostly keyed by subtopic:
`subtopics` + `pending_queries[subtopic]` → `search_results[subtopic]` (`SearchResult`, only URLs new for that subtopic, with Tavily's copy of the page in `content`) → `documents[subtopic]` (`Document` with a run-unique `id`, accumulating across passes; the summarizer drops irrelevant ones and fills `summary`) → `bullets[subtopic]` (`Bullet` with `source_ids` citing document ids) → `critique`/`needs_revision` → `report`. `seen_urls[subtopic]` remembers what each subtopic has already searched up.

State fields have no reducers, so a node's returned value replaces the old one: nodes that accumulate (`documents`, `bullets`, `seen_urls`) must return the merged result. Don't mutate state objects in place; use `model_copy(update=...)`.

**Agent convention** (`agents/*.py`): each agent is an `async def xxx_fn(state: ResearchState) -> dict` that returns only the state keys it updates, wrapped as `XxxAgent = RunnableLambda(xxx_fn)` and registered as a graph node. Agents fan out per subtopic/document with `asyncio.gather`.

**Shared modules:**
- `config.py` — model names, the `ChatGroq` instances (`LLM_PLANNER`, `LLM_SUMMARIZER`, `LLM_CRITIQUER`, `LLM_WRITER`), rate-limit settings (`MAX_CONCURRENT_LLM_CALLS`, retries, timeout), `STRUCTURED_OUTPUT_METHOD`, and guardrail/tuning constants (`MAX_TOPIC_CHARS`, `MAX_SUBTOPICS`, `MAX_TOTAL_SUBTOPICS`, `MAX_FOLLOW_UP_QUERIES`, `MAX_SEARCH_RESULTS`, `EXCLUDED_DOMAINS`, `DATE_FILTER_MAX_YEARS_AGO`, `MIN_SEARCH_SCORE`, `MAX_CHARS_PER_DOCUMENT`, `MIN_WORDS_PER_DOCUMENT`, fetch limits, `MAX_REVISIONS`). Importing `config` builds the Groq clients, which needs `GROQ_API_KEY`, so `load_dotenv()` and the key check run before `config`/`graph`/`agents` are imported (see `main.py`).
- `tools/llm.py` — **every LLM call goes through `invoke_structured(llm, Schema, prompt, what)` or `invoke_text(...)`.** They apply the per-loop semaphore, return `None` on one-off failures (logged as `[!] LLM call failed`, counted in `failed_calls`), and raise `ServiceError` for errors every later call would hit too (bad key, missing/decommissioned model, daily quota). Callers must handle `None`.
- `tools/prompts.py` — every `PromptTemplate`. Structured replies (planner, map, reduce, critique) use Groq strict JSON-schema outputs; each schema is a Pydantic model next to its agent (`ResearchPlan`, `PageSummary`, `BulletList`, `Critique`), and its field descriptions are sent to the model, so prompt wording and schema fields must change together. Untrusted web text (and notes derived from it) goes inside tags, passed through `escape_untrusted()`, with `UNTRUSTED_CONTENT_NOTE` in the prompt.
- `tools/search_api.py` — Tavily search via `AsyncTavilyClient`, created on first use. Requests Tavily's own copy of each page (`include_raw_content`), excludes `EXCLUDED_DOMAINS` (also filtered in code), drops results scoring below `MIN_SEARCH_SCORE` (keyword-matched junk) before anything is fetched or summarized, and `search_date_range()` limits a topic about one recent year ("... in 2025") to pages published from that year to March 31 of the next.
- `tools/time_frame.py` — `topic_year()` finds the single year a topic asks about; it drives the search date window and `time_frame_rule()` in the map and writer prompts, which keeps later events out of the summaries and report. One-off errors return `[]`; a rejected key or exhausted plan raises `ServiceError`.
- `tools/web_loader.py` — httpx + BeautifulSoup page fetch with guardrails: only public http(s) hosts (resolved IPs are checked, and redirects are followed by hand so every hop is checked), HTML/plain-text only, gzip decoded with a size cap, a per-page deadline. Strips script/style/nav/footer/aside, form controls and page-level `<header>`s, and truncates to `MAX_CHARS_PER_DOCUMENT`. Errors return `""` instead of raising; the retriever then falls back to the search result's `content` (this is how blocked sites and PDFs get read).
- `tools/errors.py` — `ServiceError`; `main.py` catches it and exits 1 with the message.

## Citations

The retriever makes no LLM calls: it gives each fetched page a `Document.id` (unique across passes). The summarizer's map step judges relevance on the whole page and summarizes it in one structured call (`PageSummary`), dropping pages that are clearly off-topic. The reduce step must cite `source_ids`; `_clean_bullets` drops bullets that cite no document of their subtopic. The writer renumbers cited pages 1..N by URL, feeds only subtopics with findings (bullets with `[n]` markers) to the LLM, strips any references section or out-of-range `[n]` the model writes, and appends `## Research gaps` (subtopics without findings) and `## References` itself, so neither depends on the model. If nothing at all is cited, the writer returns no report rather than writing from no evidence.

## Revisions and rate limits

The critiquer increments `revision_number`, and `should_revise_or_finish` only reads it. LangGraph doesn't persist state changes made inside routing functions, so don't move the increment there. With `MAX_REVISIONS = 2`, there is at most one re-search. A revision searches the critic's `follow_up_queries` (attached to existing subtopics, or new ones up to `MAX_TOTAL_SUBTOPICS`) plus a fresh query for every subtopic still without findings (`_queue_gap_searches`; the critic often calls research incomplete without suggesting searches), skips URLs a subtopic has already seen, and only re-summarizes subtopics that got new documents; a failed reduce keeps the earlier bullets.

Groq's free tier is about 8,000 tokens/min. LLM concurrency is capped by `MAX_CONCURRENT_LLM_CALLS` (enforced in `tools/llm.py`, one semaphore per event loop), and the clients use `max_retries` to retry 429 errors. Don't call `llm.ainvoke` directly in new code; use the `tools/llm.py` helpers so the cap and error handling apply.
