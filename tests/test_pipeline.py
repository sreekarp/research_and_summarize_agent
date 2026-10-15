"""End-to-end runs of the whole graph against the fake services."""
import re
from datetime import date

import pytest

from fakes import BAD_REQUEST, FakeServices, run_pipeline


@pytest.fixture
async def happy():
    services = FakeServices()
    code, log, err, report = await run_pipeline(services)
    assert code == 0, err
    return services, log, report


async def test_planner_output_is_cleaned(happy):
    _, log, _ = happy
    assert "['Cost trends', 'Grid integration', 'Policy']" in log  # duplicate and blank subtopics dropped


async def test_every_structured_call_uses_strict_json_schema(happy):
    services, _, _ = happy
    assert services.strict_ok


async def test_one_revision_runs_the_critics_follow_ups(happy):
    services, log, _ = happy
    assert log.count("Decision: Revising") == 1
    assert "Revision Needed (incomplete: 3 follow-up searches, 0 subtopics without findings re-searched)" in log
    assert "[Environmental impact] Kept 1 relevant documents and generated 2 bullet points." in log  # critic's new subtopic
    assert services.llm_calls["Critique"] == 2 and services.llm_calls["writer"] == 1


async def test_pages_are_fetched_and_summarized_once(happy):
    services, _, _ = happy
    assert services.fetches["https://ex.com/cost1"] == 1  # found by three subtopics across two passes
    assert services.llm_calls["PageSummary"] == 9  # 6 documents in pass 1 + 3 new ones, none redone
    assert services.llm_calls["BulletList"] == 4  # 2 subtopics in pass 1 + the 2 that changed


async def test_a_page_found_by_several_subtopics_is_judged_for_each(happy):
    _, log, _ = happy
    assert "Kept as relevant for 'Grid integration': https://ex.com/cost1" in log
    assert "Kept as relevant for 'Policy': https://ex.com/cost1" in log
    assert "Discarded as irrelevant for 'Policy': https://ex.com/policy-irrelevant" in log


async def test_fetch_guardrails(happy):
    services, log, _ = happy
    assert not any(host in url for url in services.fetches for host in ("localhost", "127.0.0.1", "internal.ex.com"))
    assert "http://localhost/admin: blocked non-public address" in log
    assert "https://ex.com/redirect: blocked non-public address" in log  # the redirect hop to 127.0.0.1
    assert not any("#" in url for url in services.fetches)
    assert any("+https://github.com/sreekarp/research_and_summarize_agent" in ua for ua in services.user_agents)


async def test_pdf_is_read_from_the_search_engines_copy(happy):
    _, log, report = happy
    assert "unsupported content type 'application/pdf'" in log
    assert "[~] Using the search engine's copy of https://ex.com/report.pdf" in log
    assert "<https://ex.com/report.pdf>" in report


async def test_search_requests(happy):
    services, log, _ = happy
    assert all(r.get("include_raw_content") == "text" for r in services.tavily_requests)
    assert all("facebook.com" in r.get("exclude_domains", []) for r in services.tavily_requests)
    assert "facebook" not in log  # also filtered in code
    assert not any("start_date" in r for r in services.tavily_requests)  # no year in the topic


async def test_prompts_fence_untrusted_web_text(happy):
    services, _, _ = happy
    page_prompt = services.prompts_for("PageSummary")[0]
    assert "<document>" in page_prompt and "untrusted" in page_prompt
    assert "evil()" not in page_prompt and "menu links" not in page_prompt and "SITE BANNER" not in page_prompt
    assert "HEADLINE 2024-05-01" in page_prompt  # article header kept, relevance judged on the whole page
    assert '<source id="1">' in services.prompts_for("BulletList")[0]
    assert "untrusted" in services.prompts_for("Critique")[0] and "untrusted" in services.prompts_for("writer")[0]


async def test_writer_input_has_clean_cited_bullets(happy):
    services, log, _ = happy
    writer_prompt = services.prompts_for("writer")[0]
    assert "* Fact A [1]" in writer_prompt and "- Fact A" not in writer_prompt
    assert "[999]" not in writer_prompt and "Dropped uncited bullet" in log
    assert "## Environmental impact" in writer_prompt and "Research gaps" not in writer_prompt


async def test_report_citations_and_references(happy):
    _, _, report = happy
    assert "bogus and combo [1]." in report  # invented citation numbers removed
    assert "```" not in report
    assert report.count("## References") == 1 and "fake ref" not in report and "made.up" not in report
    assert "## Research gaps" not in report
    refs = re.findall(r"^(\d+)\. .* - <(https://ex\.com/[^>]+)>$", report, re.MULTILINE)
    assert [url for _, url in refs] == ["https://ex.com/cost1", "https://ex.com/cost2", "https://ex.com/report.pdf",
                                        "https://ex.com/grid1", "https://ex.com/policy2", "https://ex.com/env1"]
    assert [int(n) for n, _ in refs] == [1, 2, 3, 4, 5, 6]


async def test_critic_without_follow_ups_still_fills_empty_subtopics():
    class NoFollowUps(FakeServices):
        def follow_ups(self):
            return []

    services = NoFollowUps()
    code, log, _, _ = await run_pipeline(services)
    assert code == 0
    assert "Revision Needed (incomplete: 0 follow-up searches, 1 subtopics without findings re-searched)" in log
    assert any(r["query"] == "Policy Solar power" for r in services.tavily_requests)
    assert "[Policy] Kept 1 relevant documents" in log and "## Policy" in services.prompts_for("writer")[0]


async def test_subtopic_without_sources_is_listed_as_a_research_gap():
    class PolicyNeverRelevant(FakeServices):
        def relevant(self, prompt):
            return "Subtopic: Policy" not in prompt and super().relevant(prompt)

    services = PolicyNeverRelevant()
    code, _, _, report = await run_pipeline(services)
    assert code == 0
    assert "## Policy" not in services.prompts_for("writer")[0]
    gaps = report.split("## Research gaps")[1].split("## References")[0]
    assert "* Policy" in gaps


async def test_topic_about_a_recent_year_limits_the_search_window():
    year = date.today().year - 1
    services = FakeServices()
    _, log, _, _ = await run_pipeline(services, topic=f"Solar power in {year}")
    end = min(date(year + 1, 3, 31), date.today()).isoformat()
    assert services.tavily_requests
    assert all(r.get("start_date") == f"{year}-01-01" and r.get("end_date") == end for r in services.tavily_requests)
    assert f"Limiting searches to pages published {year}-01-01 to {end}" in log
    rule = f"The research is about {year}: keep facts about {year}"
    assert rule in services.prompts_for("PageSummary")[0] and rule in services.prompts_for("writer")[0]


async def test_older_year_keeps_the_time_frame_rule_but_not_the_date_filter():
    services = FakeServices()
    await run_pipeline(services, topic="Solar power in 2008")
    assert not any("start_date" in r for r in services.tavily_requests)
    assert "The research is about 2008" in services.prompts_for("PageSummary")[0]


async def test_low_relevance_results_are_skipped_before_fetching():
    class LowScore(FakeServices):
        def search(self, query):
            hits = super().search(query)
            if query == "solar power grid integration":
                hits.append({"title": "Fund annual report", "url": "https://ex.com/fund-report", "content": "", "raw_content": None, "score": 0.12})
            return hits

    services = LowScore()
    _, log, _, _ = await run_pipeline(services)
    assert "[~] Skipped 1 low-relevance results for 'solar power grid integration'" in log
    assert "https://ex.com/fund-report" not in services.fetches
    assert not any("fund-report" in prompt for _, prompt in services.prompts)


async def test_failed_reduce_on_revision_keeps_earlier_findings():
    class RevisionReduceFails(FakeServices):
        def follow_ups(self):
            return [{"subtopic": "Cost trends", "query": "solar cost outlook"}]

        def bullets(self, prompt):
            return BAD_REQUEST if "MARKER_cost3" in prompt else super().bullets(prompt)

    services = RevisionReduceFails()
    code, _, _, _ = await run_pipeline(services)
    assert code == 0
    assert "## Cost trends\n\n* Fact A" in services.prompts_for("writer")[0]
