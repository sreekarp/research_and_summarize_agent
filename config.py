from langchain_groq import ChatGroq

# Model Configurations. Groq's daily token limit is per model, so "openai/gpt-oss-20b" (also strict-mode
# capable) is a drop-in fallback when this model's daily allowance runs out.
PLANNER_MODEL = "openai/gpt-oss-120b"
SUMMARIZER_MODEL = "openai/gpt-oss-120b"
CRITIQUER_MODEL = "openai/gpt-oss-120b"
WRITER_MODEL = "openai/gpt-oss-120b"

# Groq's free tier allows ~8000 tokens/min: retry 429s (the client honors retry-after)
# and keep reasoning short, since reasoning tokens count toward the limit.
LLM_MAX_RETRIES = 6
LLM_REASONING_EFFORT = "low"
# Without a timeout a stalled request never fails, so its retries never start
LLM_TIMEOUT_SECONDS = 60

# "json_schema" uses Groq's strict structured outputs, so replies always match the schema.
# Strict mode needs a gpt-oss model; switch to "function_calling" for other models.
STRUCTURED_OUTPUT_METHOD = "json_schema"

_LLM_OPTIONS = dict(max_retries=LLM_MAX_RETRIES, reasoning_effort=LLM_REASONING_EFFORT, timeout=LLM_TIMEOUT_SECONDS)
LLM_PLANNER = ChatGroq(model_name=PLANNER_MODEL, temperature=0, **_LLM_OPTIONS)
LLM_SUMMARIZER = ChatGroq(model_name=SUMMARIZER_MODEL, temperature=0, **_LLM_OPTIONS)
LLM_CRITIQUER = ChatGroq(model_name=CRITIQUER_MODEL, temperature=0, **_LLM_OPTIONS)
# Low temperature keeps the writer close to the cited bullet points
LLM_WRITER = ChatGroq(model_name=WRITER_MODEL, temperature=0.3, **_LLM_OPTIONS)

# Caps parallel LLM calls across all agents (every call goes through tools/llm.py). On the free tier the
# per-minute token limit is the bottleneck anyway, and with 2 calls in flight one can lose every retry to
# the other; raise this on a paid tier.
MAX_CONCURRENT_LLM_CALLS = 1

# Input Configuration
MAX_TOPIC_CHARS = 300

# Planner / Critiquer Configuration
MAX_SUBTOPICS = 5          # the planner's output is clamped to this
MAX_TOTAL_SUBTOPICS = 7    # cap once the critiquer adds subtopics for missing angles
MAX_FOLLOW_UP_QUERIES = 3  # critic-suggested searches per revision (subtopics without findings are re-searched on top)

# Search Configuration
MAX_SEARCH_RESULTS = 5
# Social media and video pages rarely contain citable text
EXCLUDED_DOMAINS = ["facebook.com", "instagram.com", "x.com", "twitter.com", "tiktok.com",
                    "youtube.com", "reddit.com", "linkedin.com", "pinterest.com", "quora.com"]
# A topic like "... in 2025" limits searches to pages published that year (plus three months), but only for
# recent years: for older years most useful pages are look-back analyses written later
DATE_FILTER_MAX_YEARS_AGO = 2
# Tavily's relevance score (0-1). Measured on a live run: useful pages scored 0.49-0.82, keyword-matched
# junk (annual reports, tax forms, unrelated live blogs) 0.33 or lower
MIN_SEARCH_SCORE = 0.35

# Retriever Configuration
MAX_CHARS_PER_DOCUMENT = 4000
MIN_WORDS_PER_DOCUMENT = 50
FETCH_TIMEOUT_SECONDS = 10      # per network operation (connect, each read)
FETCH_DEADLINE_SECONDS = 20     # for a whole page, so a slow-drip server can't stall the run
MAX_DOWNLOAD_BYTES = 2_000_000
MAX_REDIRECTS = 5

# Graph Configuration
MAX_REVISIONS = 2
