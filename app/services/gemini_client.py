import json
import re
import time
from functools import lru_cache
from google import genai
from google.genai import errors, types

from app.config import get_settings

# Temporary overload errors (HTTP 500/503) are retried with these waits (seconds).
RETRY_DELAYS = (3, 8, 20)
# A per-minute quota 429 is retried once if Gemini asks us to wait at most this long.
MAX_QUOTA_WAIT = 65

class QuotaExceeded(RuntimeError):
    """Raised on HTTP 429 so the caller can fall back to another model."""

@lru_cache
def _client(api_key: str) -> genai.Client:
    # Keep one long-lived client. A temporary Client() can be garbage-collected
    # mid-call, which closes its HTTP connection ("client has been closed").
    return genai.Client(api_key=api_key)

def _quota_info(exc: errors.APIError) -> tuple[bool, float | None]:
    """Return (is_daily_quota, retry_delay_seconds) from a 429 error body."""
    details = exc.details.get("error", {}).get("details", []) if isinstance(exc.details, dict) else []
    daily, delay = False, None
    for item in details:
        if not isinstance(item, dict):
            continue
        for violation in item.get("violations", []):
            if "PerDay" in str(violation.get("quotaId", "")):
                daily = True
        match = re.fullmatch(r"([\d.]+)s", str(item.get("retryDelay", "")))
        if match:
            delay = float(match.group(1))
    return daily, delay

def _friendly_error(model: str, exc: errors.APIError) -> RuntimeError:
    if exc.code == 429:
        daily, _ = _quota_info(exc)
        if daily:
            return QuotaExceeded(
                f"Gemini daily quota used up for '{model}'. It resets at midnight Pacific time. "
                "Until then, set GEMINI_OUTLINE_MODEL / GEMINI_STORY_MODEL (or GEMINI_FALLBACK_MODEL) "
                "in .env to a different model, or enable billing on your Google AI project. "
                "Details: " + str(exc))
        return QuotaExceeded(
            f"Gemini rate limit hit for '{model}' (still failing after waiting). Try again in a "
            "minute, or set GEMINI_FALLBACK_MODEL in .env. Details: " + str(exc))
    if exc.code == 404:
        return RuntimeError(
            f"Gemini model '{model}' is not available to this API key. Change "
            "GEMINI_OUTLINE_MODEL / GEMINI_STORY_MODEL in .env. Details: " + str(exc))
    if exc.code in (500, 503):
        return RuntimeError(
            f"Gemini '{model}' is overloaded right now (still failing after retries). "
            "Please try again in a few minutes. Details: " + str(exc))
    return RuntimeError(f"Gemini request to '{model}' failed: {exc}")

def generate_json(model: str, prompt: str, temperature: float) -> dict:
    """Call Gemini and return the response parsed as a JSON object.

    If the model's quota is exhausted and GEMINI_FALLBACK_MODEL is set, retry with that model.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured. Add it to .env.")
    fallback = settings.gemini_fallback_model.strip()
    try:
        return _generate_json(settings.gemini_api_key, model, prompt, temperature)
    except QuotaExceeded as exc:
        if not fallback or fallback == model:
            raise
        try:
            return _generate_json(settings.gemini_api_key, fallback, prompt, temperature)
        except QuotaExceeded as fallback_exc:
            raise QuotaExceeded(f"{exc}\nFallback model also failed: {fallback_exc}") from fallback_exc

def _generate_json(api_key: str, model: str, prompt: str, temperature: float) -> dict:
    waited_for_quota = False
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            response = _client(api_key).models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                ),
            )
            break
        except errors.APIError as exc:
            if exc.code in (500, 503) and attempt < len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt])
                continue
            if exc.code == 429 and not waited_for_quota and attempt < len(RETRY_DELAYS):
                daily, delay = _quota_info(exc)
                if not daily and delay is not None and delay <= MAX_QUOTA_WAIT:
                    waited_for_quota = True
                    time.sleep(delay + 1)
                    continue
            raise _friendly_error(model, exc) from exc
    if not response.text:
        raise ValueError(f"Gemini ({model}) returned an empty response; it may have been blocked.")
    return extract_json(response.text)

def extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Gemini did not return valid JSON.")
    data = json.loads(text[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("Gemini returned JSON that is not an object.")
    return data
