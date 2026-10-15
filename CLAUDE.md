# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py "Some research topic"   # defaults to "Impact of generative AI on education"
```

Requires a `.env` in the repo root with `TAVILY_API_KEY` and `GROQ_API_KEY` (`.env` is gitignored). There is no test suite, linter, or build step.

## Architecture

A LangGraph `StateGraph` pipeline of LLM "agents" that researches a topic and prints a Markdown report.

**Flow** (`graph/graph_builder.py`):
`planner → searcher → retriever → summarizer → critiquer → (searcher again | writer) → END`.
If the planner produces no subtopics, the graph ends immediately.

**State** (`graph/state.py`): a single Pydantic `ResearchState`. Each stage reads earlier fields and fills its own, mostly keyed by subtopic:
`subtopics` → `search_results[subtopic]` (`{title, href}` dicts) → `documents[subtopic]` (`{text, source}` dicts) → `bullets[subtopic]` → `critique`/`needs_revision` → `report`.

**Agent convention** (`agents/*.py`): each agent is an `async def xxx_fn(state: ResearchState) -> dict` that returns only the state keys it updates, wrapped as `XxxAgent = RunnableLambda(xxx_fn)` and registered as a graph node. Agents fan out per subtopic/document with `asyncio.gather`.

**Shared modules:**
- `config.py` — model names, the `ChatGroq` instances (`LLM_PLANNER`, `LLM_SUMMARIZER`, `LLM_CRITIQUER`, `LLM_WRITER`), rate-limit settings (`LLM_SEMAPHORE`, retries), and tuning constants (`MAX_SEARCH_RESULTS`, `MAX_CHARS_PER_DOCUMENT`, `MAX_REVISIONS`). The retriever's relevance check reuses `LLM_PLANNER`. `RELEVANCE_CHECK_THRESHOLD` is defined but unused.
- `tools/prompts.py` — every `PromptTemplate`. Agents parse the LLM output as plain text, so prompt format and parsing code must change together:
  - planner: Python list literal, optionally in a ```` ```python ```` fence, parsed with `ast.literal_eval`
  - relevance check: the substring `"irrelevant"` discards a doc
  - summarizer: map (one summary per doc) then reduce (bullets split on newlines)
  - critiquer: first line = critique, last line containing `"incomplete"` triggers revision
- `tools/search_api.py` — Tavily search (sync client run via `asyncio.to_thread`). The client is created at import time and reads `TAVILY_API_KEY`, so `load_dotenv()` has to run before `graph`/`agents` are imported (see `main.py`).
- `tools/web_loader.py` — httpx + BeautifulSoup page fetch; strips script/style/nav/footer/aside and truncates to `MAX_CHARS_PER_DOCUMENT`. Errors return `""` instead of raising.

## Revisions and rate limits

The critiquer increments `revision_number`, and `should_revise_or_finish` only reads it. LangGraph doesn't persist state changes made inside routing functions, so don't move the increment there. With `MAX_REVISIONS = 2`, there is at most one re-search.

Groq's free tier is about 8,000 tokens/min. Parallel LLM calls in the retriever and summarizer are wrapped in `async with LLM_SEMAPHORE`, and the clients use `max_retries` to retry 429 errors. New fan-out LLM calls should use the semaphore too.
