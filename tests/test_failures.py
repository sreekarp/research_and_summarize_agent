"""One-off failures degrade gracefully; failures every later call would hit stop the run with a clear message."""
import httpx

from fakes import BAD_REQUEST, NO_RETRY, FakeServices, run_pipeline


async def test_planner_failure_exits_1_with_an_accurate_message():
    class PlannerFails(FakeServices):
        def plan(self):
            return BAD_REQUEST

    code, _, err, _ = await run_pipeline(PlannerFails())
    assert code == 1 and "the planner returned no subtopics" in err


async def test_no_report_is_written_without_evidence():
    class AllIrrelevant(FakeServices):
        def relevant(self, prompt):
            return False

    services = AllIrrelevant()
    code, log, err, _ = await run_pipeline(services)
    assert code == 1 and "none of the fetched pages produced cited findings" in err
    assert "FINAL RESEARCH REPORT" not in log
    assert services.llm_calls["writer"] == 0


async def test_writer_failure_falls_back_to_the_cited_notes():
    class WriterFails(FakeServices):
        def writer(self, prompt):
            return BAD_REQUEST

    code, log, _, report = await run_pipeline(WriterFails())
    assert code == 0
    assert report.startswith("# Solar power") and "* Fact A [1]" in report and "## References" in report
    assert "1 LLM call(s) failed" in log


async def test_reduce_and_critique_failures_dont_crash_the_run():
    class Flaky(FakeServices):
        def bullets(self, prompt):
            return BAD_REQUEST

        def critique(self):
            return BAD_REQUEST

    code, log, err, _ = await run_pipeline(Flaky())
    assert code == 1 and "Traceback" not in err
    # Gap-filling doesn't depend on the critic
    assert "Revision Needed (critique unavailable: 0 follow-up searches, 3 subtopics without findings re-searched)" in log


async def test_malformed_json_is_retried_once():
    class JsonGlitch(FakeServices):
        glitched = False

        def page_summary(self, prompt):
            if "MARKER_cost2" in prompt and not self.glitched:
                self.glitched = True
                return httpx.Response(400, json={"error": {"message": "Failed to generate JSON.", "type": "invalid_request_error",
                                                           "code": "json_validate_failed"}})
            return super().page_summary(prompt)

    code, log, _, _ = await run_pipeline(JsonGlitch())
    assert code == 0
    assert "[~] Retrying summary of https://ex.com/cost2" in log
    assert "Kept as relevant for 'Cost trends': https://ex.com/cost2" in log
    assert "LLM call(s) failed" not in log


async def test_rejected_groq_key_stops_the_run():
    class BadKey(FakeServices):
        def plan(self):
            return httpx.Response(401, json={"error": {"message": "Invalid API Key", "type": "invalid_request_error", "code": "invalid_api_key"}})

    code, _, err, _ = await run_pipeline(BadKey())
    assert code == 1 and "Stopped: Groq rejected the request (planner)" in err and "Invalid API Key" in err


async def test_decommissioned_model_stops_the_run_early():
    class ModelGone(FakeServices):
        def page_summary(self, prompt):
            return httpx.Response(400, json={"error": {"message": "The model has been decommissioned", "type": "invalid_request_error",
                                                       "code": "model_decommissioned"}})

    services = ModelGone()
    code, _, err, _ = await run_pipeline(services)
    assert code == 1 and "decommissioned" in err
    assert services.llm_calls["Critique"] == 0


async def test_daily_token_quota_stops_the_run():
    class DailyQuota(FakeServices):
        def page_summary(self, prompt):
            return httpx.Response(429, headers=NO_RETRY, json={"error": {
                "message": "Rate limit reached on tokens per day (TPD): Limit 200000, Used 199999",
                "type": "tokens", "code": "rate_limit_exceeded"}})

    code, _, err, _ = await run_pipeline(DailyQuota())
    assert code == 1 and "tokens per day" in err


async def test_per_minute_rate_limit_is_a_one_off_failure():
    class MinuteQuota(FakeServices):
        def page_summary(self, prompt):
            return httpx.Response(429, headers=NO_RETRY, json={"error": {
                "message": "Rate limit reached on tokens per minute (TPM)", "type": "tokens", "code": "rate_limit_exceeded"}})

    _, log, err, _ = await run_pipeline(MinuteQuota())
    assert "Stopped" not in err
    assert "LLM call failed (summary of" in log


async def test_rejected_tavily_key_stops_the_run():
    class BadTavilyKey(FakeServices):
        def tavily(self, request):
            return httpx.Response(401, json={"detail": {"error": "Unauthorized: missing or invalid API key."}})

    code, _, err, _ = await run_pipeline(BadTavilyKey())
    assert code == 1 and "Stopped: Tavily rejected the search (InvalidAPIKeyError)" in err
