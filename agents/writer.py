import re
from typing import List
from langchain_core.runnables import RunnableLambda
from config import LLM_WRITER
from tools.llm import invoke_text
from tools.prompts import writer_prompt, escape_untrusted, time_frame_rule
from graph.state import ResearchState, Document

# Citation markers like " [2]" or "[1, 3]": 1-3 digits so "[2023]" survives, not glued to a word so
# "data[0]" survives, not followed by "(" so a markdown link survives. Anchored at the start of
# a whitespace run so long runs of spaces can't cause slow backtracking.
_CITATION = re.compile(r"(?<![ \t])([ \t]*)(?<![\w\])])\[(\d{1,3}(?:[ \t]*,[ \t]*\d{1,3})*)\](?!\()")
# A references section the model wrote despite the prompt; the real one is built from the documents.
# Only matches when it is the last section, so a subtopic titled "Sources" survives.
_MODEL_REFERENCES = re.compile(
    r"^#{1,6}[ \t]*(?:references|sources|bibliography|works cited)[ \t]*(?::[ \t]*)?$(?:(?!^#).)*\Z",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
# gpt-oss's native citation style, "【3】" or "【3†source】": normalized to "[3]" so the checks below apply to it
_NATIVE_CITATION = re.compile(r"【(\d{1,3}(?:\s*[,，、]\s*\d{1,3})*)(?:†[^】]*)?】")
_OTHER_NATIVE_MARKER = re.compile(r"(?<![ \t])[ \t]*【[^】\n]{0,80}】")
_CODE_FENCE = re.compile(r"\A```(?:markdown|md)?[ \t]*\n(.*)\n```[ \t]*\Z", re.DOTALL)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")  # keeps \t and \n
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_\[\]<>!|])")


def _number_sources(state: ResearchState) -> tuple[dict[int, int], List[Document]]:
    """Number the cited pages 1..N in order of first citation. A page used by two subtopics gets one number."""
    docs_by_id = {doc.id: doc for docs in state.documents.values() for doc in docs}
    numbers, numbers_by_url, cited = {}, {}, []
    for subtopic in state.subtopics:
        for bullet in state.bullets.get(subtopic, []):
            for doc_id in bullet.source_ids:
                doc = docs_by_id.get(doc_id)
                if doc is None or doc_id in numbers:
                    continue
                if doc.url not in numbers_by_url:
                    cited.append(doc)
                    numbers_by_url[doc.url] = len(cited)
                numbers[doc_id] = numbers_by_url[doc.url]
    return numbers, cited

def _format_summary_for_writer(state: ResearchState, numbers: dict[int, int]) -> str:
    text = ""
    for subtopic in state.subtopics:
        bullets = state.bullets.get(subtopic, [])
        if not bullets:
            continue
        text += f"## {subtopic}\n\n"
        for bullet in bullets:
            markers = dict.fromkeys(numbers[i] for i in bullet.source_ids if i in numbers)
            text += f"* {bullet.text} " + "".join(f"[{n}]" for n in markers) + "\n"
        text += "\n"
    return text.strip()

def _format_gaps(state: ResearchState) -> str:
    """Added by code rather than left to the writer, so a reader always learns which parts are missing."""
    gaps = [subtopic for subtopic in state.subtopics if not state.bullets.get(subtopic)]
    if not gaps:
        return ""
    return ("## Research gaps\n\nNo reliable sources were found for these parts of the topic, so this report "
            "does not cover them:\n\n" + "\n".join(f"* {subtopic}" for subtopic in gaps) + "\n\n")

def _clean_draft(draft: str, source_count: int) -> str:
    """Unwrap a code fence, cut any model-written references section and remove citation numbers that don't exist."""
    fenced = _CODE_FENCE.match(draft.strip())
    draft = fenced.group(1) if fenced else draft
    draft = _MODEL_REFERENCES.sub("", draft).rstrip()
    draft = _NATIVE_CITATION.sub(lambda m: "[" + re.sub(r"\s*[,，、]\s*", ", ", m.group(1)) + "]", draft)
    draft = _OTHER_NATIVE_MARKER.sub("", draft)

    def keep_valid(match: re.Match) -> str:
        valid = [n for n in re.split(r"[ \t]*,[ \t]*", match.group(2)) if 1 <= int(n) <= source_count]
        return f"{match.group(1)}[{', '.join(valid)}]" if valid else ""

    return _CITATION.sub(keep_valid, draft)

def _format_references(cited: List[Document]) -> str:
    lines = []
    for n, doc in enumerate(cited, start=1):
        # Titles come from the web: escape them so they can't add links, images or HTML to the report
        title = _MARKDOWN_SPECIAL.sub(r"\\\1", doc.title) if doc.title else ""
        url = doc.url.replace(" ", "%20").replace("<", "%3C").replace(">", "%3E")
        lines.append(f"{n}. {title or url} - <{url}>")
    return "## References\n\n" + "\n".join(lines)

async def writer_fn(state: ResearchState) -> dict:
    """Generate the final markdown report from the cited bullet points. Returns no report if nothing was found."""
    numbers, cited = _number_sources(state)
    if not cited:
        # Writing without evidence would only produce made-up content
        print("[!] No cited findings to write from")
        return {"report": None}

    summary_text = _format_summary_for_writer(state, numbers)
    prompt = writer_prompt.invoke({
        "topic": state.topic,
        "time_frame": time_frame_rule(state.topic),
        "summary_text": escape_untrusted(summary_text)
    })
    draft = await invoke_text(LLM_WRITER, prompt, "report")

    if draft:
        body = _clean_draft(draft, len(cited))
    else:
        print("[!] Writer failed; using the collected notes as the report")
        body = f"# {state.topic}\n\n{summary_text}"

    print("--- Final Report Generated ---\n")
    report = f"{body}\n\n{_format_gaps(state)}{_format_references(cited)}\n"
    return {"report": _CONTROL_CHARS.sub("", report)}

WriterAgent = RunnableLambda(writer_fn)
