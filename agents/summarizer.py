import asyncio
import re
from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableLambda
from config import LLM_SUMMARIZER
from tools.llm import invoke_structured
from tools.prompts import map_summarize_prompt, reduce_bullets_prompt, escape_untrusted, time_frame_rule
from graph.state import ResearchState, Document, Bullet

_LIST_MARKER = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
# "[3]" or "[1, 2]" (1-3 digits only, so a bracketed year like [2021] is kept), or gpt-oss's native "【3】"/"【3†source】"
_CITATION_MARKER = re.compile(r"(?<![ \t])[ \t]*(?:\[\d{1,3}(?:[ \t]*,[ \t]*\d{1,3})*\]|【[^】\n]{0,80}】)")


class PageSummary(BaseModel):
    """Whether a page is about the subtopic and, if so, its key facts."""
    relevant: bool = Field(description="False only if the page clearly has no information about the subtopic")
    summary: str = Field(description="Key facts about the subtopic from the page; empty if not relevant")


class BulletList(BaseModel):
    """Consolidated findings for one subtopic."""
    bullets: List[Bullet] = Field(description="3-5 bullet points")


def _clean_bullets(bullets: List[Bullet], valid_ids: set[int], subtopic: str) -> List[Bullet]:
    """Strip list symbols and citation markers from the text, and drop bullets that cite none of this subtopic's sources."""
    cleaned = []
    for bullet in bullets:
        text = _CITATION_MARKER.sub("", _LIST_MARKER.sub("", bullet.text)).strip()
        source_ids = sorted({i for i in bullet.source_ids if i in valid_ids})
        if not text:
            continue
        if not source_ids:
            print(f"[!] Dropped uncited bullet for '{subtopic}': {text[:80]}")
            continue
        cleaned.append(Bullet(text=text, source_ids=source_ids))
    return cleaned

async def _map_summarize_doc(document: Document, subtopic: str, topic: str) -> Optional[Document]:
    """Judge a new document's relevance on the whole page and summarize it. Returns None if it is irrelevant;
    if the call fails, the document stays unsummarized so the next pass retries it."""
    if document.summary:
        return document
    prompt = map_summarize_prompt.invoke({
        "topic": topic,
        "subtopic": subtopic,
        "time_frame": time_frame_rule(topic),
        "text": escape_untrusted(document.text)
    })
    result = await invoke_structured(LLM_SUMMARIZER, PageSummary, prompt, f"summary of {document.url}")
    if result is None:
        return document
    if not result.relevant:
        print(f"[!] Discarded as irrelevant for '{subtopic}': {document.url}")
        return None
    summary = result.summary.strip()
    if not summary:
        return document
    print(f"[+] Kept as relevant for '{subtopic}': {document.url}")
    return document.model_copy(update={"summary": summary})

async def _summarize_subtopic(subtopic: str, topic: str, docs: List[Document], previous_bullets: List[Bullet]) -> tuple[List[Document], List[Bullet]]:
    """Map each new document to a summary, then reduce all summaries to cited bullets."""
    already_summarized = {doc.id for doc in docs if doc.summary}
    mapped = await asyncio.gather(*(_map_summarize_doc(doc, subtopic, topic) for doc in docs))
    docs = [doc for doc in mapped if doc]
    summarized = [doc for doc in docs if doc.summary]
    if previous_bullets and all(doc.id in already_summarized for doc in summarized):
        return docs, previous_bullets  # nothing new since the last pass
    if not summarized:
        return docs, []

    reduce_prompt = reduce_bullets_prompt.invoke({
        "subtopic": subtopic,
        "summaries": "\n\n".join(f'<source id="{doc.id}">\n{escape_untrusted(doc.summary)}\n</source>' for doc in summarized)
    })
    result = await invoke_structured(LLM_SUMMARIZER, BulletList, reduce_prompt, f"bullets for '{subtopic}'")
    bullets = _clean_bullets(result.bullets, {doc.id for doc in summarized}, subtopic) if result else []
    # A failed reduce on a revision pass keeps the earlier findings instead of wiping them
    # (they only cite documents that are still summarized)
    return docs, bullets or previous_bullets

async def summarizer_fn(state: ResearchState) -> dict:
    """Summarize content for each subtopic in parallel using a map-reduce approach."""
    subtopics = list(state.documents)
    outcomes = await asyncio.gather(*(
        _summarize_subtopic(subtopic, state.topic, state.documents[subtopic], state.bullets.get(subtopic, []))
        for subtopic in subtopics
    ))
    # Irrelevant documents are dropped here, so nothing can cite them
    documents = {subtopic: docs for subtopic, (docs, _) in zip(subtopics, outcomes)}
    bullets_by_topic = {subtopic: bullets for subtopic, (_, bullets) in zip(subtopics, outcomes)}

    print("\n--- Summarization Complete ---")
    for subtopic, bullets in bullets_by_topic.items():
        relevant = sum(1 for doc in documents[subtopic] if doc.summary)
        print(f"[{subtopic}] Kept {relevant} relevant documents and generated {len(bullets)} bullet points.")
    print("--------------------------\n")

    return {"documents": documents, "bullets": bullets_by_topic}

SummarizerAgent = RunnableLambda(summarizer_fn)
