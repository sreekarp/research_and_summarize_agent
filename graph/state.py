# graph/state.py
from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    title: str = ""
    url: str
    content: str = ""  # the search engine's copy of the page, used when fetching it ourselves fails


class Document(BaseModel):
    """A fetched page that passed the relevance check."""
    id: int  # unique across the run; bullets cite documents by this id
    url: str
    title: str = ""
    text: str
    summary: Optional[str] = None  # filled by the summarizer's map step


class Bullet(BaseModel):
    """One finding, backed by the documents it cites."""
    text: str = Field(description="One factual statement, without citation markers or list symbols")
    source_ids: List[int] = Field(description="Ids of the sources that support this statement")


class ResearchState(BaseModel):
    """The state of the research process."""
    topic: str
    revision_number: int = 0
    max_revisions: int

    # Planner state (the critiquer can add subtopics and queries for a revision)
    subtopics: List[str] = Field(default_factory=list)
    pending_queries: Dict[str, List[str]] = Field(default_factory=dict)  # searches for the next pass, per subtopic

    # Searcher state
    search_results: Dict[str, List[SearchResult]] = Field(default_factory=dict)  # only URLs new in the latest pass
    seen_urls: Dict[str, List[str]] = Field(default_factory=dict)  # per subtopic, so a page can serve several subtopics

    # Retriever state (accumulates across passes)
    documents: Dict[str, List[Document]] = Field(default_factory=dict)

    # Summarizer state
    bullets: Dict[str, List[Bullet]] = Field(default_factory=dict)

    # Critiquer state
    critique: Optional[str] = None
    needs_revision: bool = False

    # Writer state
    report: Optional[str] = None
