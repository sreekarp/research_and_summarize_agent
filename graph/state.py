# graph/state.py
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class ResearchState(BaseModel):
    """The state of the research process."""
    topic: str
    revision_number: int = 0
    max_revisions: int
    
    # Planner state
    subtopics: List[str] = Field(default_factory=list)
    
    # Searcher state
    search_results: Dict[str, List[Dict]] = Field(default_factory=dict)
    
    # Retriever state
    documents: Dict[str, List[Dict]] = Field(default_factory=dict)
    
    # Summarizer state
    bullets: Dict[str, List[str]] = Field(default_factory=dict)
    
    # Critiquer state
    critique: Optional[str] = None
    needs_revision: bool = False  # <-- Add this line

    # Writer state
    report: Optional[str] = None