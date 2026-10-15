class ServiceError(Exception):
    """A Groq or Tavily error that every later call would hit too (bad API key, missing model,
    exhausted daily quota), so the run stops with a clear message instead of degrading call by call."""
