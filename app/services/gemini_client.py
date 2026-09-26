import json
import re
import time
from functools import lru_cache
from google import genai
from google.genai import errors, types

from app.config import get_settings

# Temporary overload errors (HTTP 500/503) are retried with these waits (seconds).
RETRY_DELAYS = (3, 8, 20)

@lru_cache
def _client(api_key: str) -> genai.Client:
    # Keep one long-lived client. A temporary Client() can be garbage-collected
    # mid-call, which closes its HTTP connection ("client has been closed").
    return genai.Client(api_key=api_key)

def _friendly_error(model: str, exc: errors.APIError) -> RuntimeError:
    if exc.code == 429:
        return RuntimeError(
            f"Gemini quota exceeded for '{model}'. Wait a minute and retry, or set a model "
            "your plan includes (e.g. gemini-3.8-flash) in .env. Details: " + str(exc))
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
    """Call Gemini and return the response parsed as a JSON object."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured. Add it to .env.")

    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            response = _client(settings.gemini_api_key).models.generate_content(
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
