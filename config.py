import asyncio
from langchain_groq import ChatGroq

# Model Configurations
PLANNER_MODEL = "openai/gpt-oss-20b"
SUMMARIZER_MODEL = "openai/gpt-oss-20b"
CRITIQUER_MODEL = "openai/gpt-oss-20b"  
WRITER_MODEL = "openai/gpt-oss-20b"     

# Groq's free tier allows ~8000 tokens/min: retry 429s (the client honors retry-after)
# and keep reasoning short, since reasoning tokens count toward the limit.
LLM_MAX_RETRIES = 6
LLM_REASONING_EFFORT = "low"

LLM_PLANNER = ChatGroq(model_name=PLANNER_MODEL, temperature=0, max_retries=LLM_MAX_RETRIES, reasoning_effort=LLM_REASONING_EFFORT)
LLM_SUMMARIZER = ChatGroq(model_name=SUMMARIZER_MODEL, temperature=0, max_retries=LLM_MAX_RETRIES, reasoning_effort=LLM_REASONING_EFFORT)
LLM_CRITIQUER = ChatGroq(model_name=CRITIQUER_MODEL, temperature=0, max_retries=LLM_MAX_RETRIES, reasoning_effort=LLM_REASONING_EFFORT)
LLM_WRITER = ChatGroq(model_name=WRITER_MODEL, temperature=0.7, max_retries=LLM_MAX_RETRIES, reasoning_effort=LLM_REASONING_EFFORT)

# Caps parallel LLM calls in the retriever and summarizer
MAX_CONCURRENT_LLM_CALLS = 2
LLM_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)


# Search Configuration
MAX_SEARCH_RESULTS = 5

# Retriever Configuration
MAX_CHARS_PER_DOCUMENT = 4000
RELEVANCE_CHECK_THRESHOLD = 0.8 # Confidence score for a doc to be relevant

# Graph Configuration
MAX_REVISIONS = 2