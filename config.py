from langchain_groq import ChatGroq

# Model Configurations
PLANNER_MODEL = "llama-3.1-8b-instant"
SUMMARIZER_MODEL = "llama-3.1-8b-instant"
CRITIQUER_MODEL = "llama-3.1-8b-instant"  
WRITER_MODEL = "llama-3.1-8b-instant"     

LLM_PLANNER = ChatGroq(model_name=PLANNER_MODEL, temperature=0)
LLM_SUMMARIZER = ChatGroq(model_name=SUMMARIZER_MODEL, temperature=0)
LLM_CRITIQUER = ChatGroq(model_name=CRITIQUER_MODEL, temperature=0)
LLM_WRITER = ChatGroq(model_name=WRITER_MODEL, temperature=0.7)


# Search Configuration
MAX_SEARCH_RESULTS = 5

# Retriever Configuration
MAX_CHARS_PER_DOCUMENT = 4000
RELEVANCE_CHECK_THRESHOLD = 0.8 # Confidence score for a doc to be relevant

# Graph Configuration
MAX_REVISIONS = 2