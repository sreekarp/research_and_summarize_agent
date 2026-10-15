import re
from typing import Optional

# "... in 2025", "during 2024": a topic about one year focuses searching, summarizing and writing on it
_TIME_FRAME = re.compile(r"\b(?:in|during|throughout|for)\s+((?:19|20)\d{2})\b", re.IGNORECASE)


def topic_year(topic: str) -> Optional[int]:
    """The single year the topic asks about, or None (no year, or more than one)."""
    years = {int(year) for year in _TIME_FRAME.findall(topic)}
    return years.pop() if len(years) == 1 else None
