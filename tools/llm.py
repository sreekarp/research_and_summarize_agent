import asyncio
import weakref
from typing import Optional, Type, TypeVar
import groq
from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, ValidationError
from config import MAX_CONCURRENT_LLM_CALLS, STRUCTURED_OUTPUT_METHOD
from tools.errors import ServiceError

T = TypeVar("T", bound=BaseModel)

# Groq reports these as 400s, but every later call would fail the same way
_FATAL_ERROR_CODES = {"invalid_api_key", "model_not_found", "model_decommissioned"}

_semaphores: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = weakref.WeakKeyDictionary()
failed_calls = 0  # calls that returned None; main reports the count


def _llm_semaphore() -> asyncio.Semaphore:
    # One per event loop: an asyncio.Semaphore only works in the loop it first waited in
    loop = asyncio.get_running_loop()
    if loop not in _semaphores:
        _semaphores[loop] = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)
    return _semaphores[loop]


def _is_fatal(error: Exception) -> bool:
    if isinstance(error, (groq.AuthenticationError, groq.PermissionDeniedError, groq.NotFoundError)):
        return True
    if isinstance(error, groq.RateLimitError):
        # Per-minute limits recover after the client's retries; a daily limit won't recover during this run
        return "per day" in str(error)
    if isinstance(error, groq.BadRequestError) and isinstance(error.body, dict):
        details = error.body.get("error", error.body)
        return isinstance(details, dict) and details.get("code") in _FATAL_ERROR_CODES
    return False


def _is_malformed_output(error: Exception) -> bool:
    """The model produced invalid JSON for the schema; a fresh attempt usually succeeds."""
    if isinstance(error, (OutputParserException, ValidationError)):
        return True
    return isinstance(error, groq.BadRequestError) and isinstance(error.body, dict) and \
        (error.body.get("error") or {}).get("code") == "json_validate_failed"


async def _call(runnable, prompt, what: str):
    global failed_calls
    async with _llm_semaphore():
        for attempt in range(2):
            try:
                return await runnable.ainvoke(prompt)
            except Exception as e:
                if _is_fatal(e):
                    raise ServiceError(f"Groq rejected the request ({what}): {e}") from e
                if attempt == 0 and _is_malformed_output(e):
                    print(f"[~] Retrying {what}: the model returned malformed output")
                    continue
                failed_calls += 1
                print(f"[!] LLM call failed ({what}): {type(e).__name__}: {str(e)[:300]}")
                return None


async def invoke_structured(llm, schema: Type[T], prompt, what: str) -> Optional[T]:
    """Call the LLM and parse its reply into `schema`. Returns None on a one-off failure, so one bad call can't end the run."""
    strict = True if STRUCTURED_OUTPUT_METHOD == "json_schema" else None
    structured_llm = llm.with_structured_output(schema, method=STRUCTURED_OUTPUT_METHOD, strict=strict)
    return await _call(structured_llm, prompt, what)


async def invoke_text(llm, prompt, what: str) -> Optional[str]:
    """Call the LLM for free text. Returns None on a one-off failure or an empty reply."""
    response = await _call(llm, prompt, what)
    if response is None:
        return None
    text = response.content.strip() if isinstance(response.content, str) else ""
    return text or None
