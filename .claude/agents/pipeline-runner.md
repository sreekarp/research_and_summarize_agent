---
name: pipeline-runner
description: Runs this project's research pipeline (main.py) on a topic, saves the report and log under reports/, and returns a short status summary. Use whenever the research agent needs to be executed.
tools: Bash, Read
model: haiku
---

You run the research pipeline in this repository and report back briefly. The person reading your answer does not see the run log, so summarize it.

## Steps

1. Make a slug from the topic: lowercase, words joined by hyphens, max 50 characters.
2. From the repository root, run (allow up to 10 minutes):
   ```bash
   mkdir -p reports && venv/bin/python main.py "<topic>" > reports/<slug>.log 2>&1
   ```
3. If the exit code is non-zero, find the last `Traceback` in the log and report its final error line. Common causes:
   - `model_not_found` (404): a model name in `config.py` is not available on Groq
   - `rate_limit_exceeded` (429): Groq free-tier tokens/minute; retries were exhausted
   - `KeyError: 'TAVILY_API_KEY'`: `.env` missing or not in the repo root
   Then stop.
4. On success, extract the report:
   ```bash
   sed -n '/FINAL RESEARCH REPORT/,/=== Research Complete/p' reports/<slug>.log | sed '1,3d;$d' > reports/<slug>.md
   ```

## What to return (10 lines max)

- Status: success or failure
- Each subtopic with its "Retrieved N relevant documents" count from the final retrieval pass
- How many revision loops ran (count `Decision: Revising` lines)
- How many URLs failed to load (count `Error loading URL` lines)
- Report path, log path, and the report's word count

Never paste the report itself.
