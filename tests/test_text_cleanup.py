"""The writer's and summarizer's cleanup of model output: citations, references, list markers."""
import time

from agents.summarizer import _clean_bullets
from agents.writer import _clean_draft, _format_references
from graph.state import Bullet, Document

DRAFT = ("# T\n\n## Sources\n\nSolar sources text [1].\n\n## Conclusion\n\nEnd [2] [7]. In [2023] prices fell; see data[0] and "
         "[1](http://x) and word [3, 7].\n[9] Next line\n\n### References:\n\n1. junk")


def test_mid_report_sources_section_survives():
    cleaned = _clean_draft(DRAFT, 3)
    assert "## Sources" in cleaned and "Solar sources text [1]." in cleaned


def test_trailing_references_and_invented_numbers_are_removed():
    cleaned = _clean_draft(DRAFT, 3)
    assert "junk" not in cleaned and "[7]" not in cleaned
    assert "End [2]." in cleaned and "word [3]." in cleaned


def test_years_code_indices_and_links_are_untouched():
    cleaned = _clean_draft(DRAFT, 3)
    assert "[2023]" in cleaned and "data[0]" in cleaned and "[1](http://x)" in cleaned


def test_removing_a_marker_at_a_line_start_keeps_the_line_break():
    assert "\nNext line" in _clean_draft(DRAFT, 3) or "\n Next line" in _clean_draft(DRAFT, 3)


def test_code_fence_is_unwrapped():
    assert _clean_draft("```markdown\n# Title\n\nText [1].\n```", 1) == "# Title\n\nText [1]."


def test_gpt_oss_native_citations_are_normalized_and_validated():
    cleaned = _clean_draft("Fact 【1】 and 【2†source】 then bad 【9】, combo 【1, 3】 and 【1，2】 and odd 【source】.", 3)
    assert cleaned == "Fact [1] and [2] then bad, combo [1, 3] and [1, 2] and odd."


def test_cleanup_regexes_stay_fast_on_degenerate_input():
    start = time.perf_counter()
    _clean_draft("# T\n" + "\n" * 30000 + "## References" + " " * 30000 + "x", 3)
    _clean_draft("a" + " " * 50000 + "b", 3)
    _clean_bullets([Bullet(text="a" + " " * 50000 + "b", source_ids=[1])], {1}, "s")
    assert time.perf_counter() - start < 1


def test_reference_titles_are_escaped_and_urls_encoded():
    refs = _format_references([Document(id=1, url="https://ex.com/a b", title="Evil](http://phish) ![x](y) <b>bold</b>", text="t")])
    line = refs.splitlines()[-1]
    assert "Evil\\](http" in line and "\\!\\[x\\]" in line and "\\<b\\>" in line
    assert line.endswith("<https://ex.com/a%20b>")


def test_bullets_lose_list_and_citation_markers_but_keep_years():
    bullets = _clean_bullets([Bullet(text="1. In [2023] prices fell [3, 4]", source_ids=[3, 4, 9]),
                              Bullet(text="2023 was big", source_ids=[3]),
                              Bullet(text="Imports rose 【3】 sharply【4†L1-L5】", source_ids=[3])], {3, 4}, "s")
    assert [b.text for b in bullets] == ["In [2023] prices fell", "2023 was big", "Imports rose sharply"]
    assert bullets[0].source_ids == [3, 4]  # 9 belongs to another subtopic


def test_bullets_citing_no_valid_source_are_dropped():
    assert _clean_bullets([Bullet(text="Uncited", source_ids=[99]), Bullet(text="  ", source_ids=[1])], {1}, "s") == []
