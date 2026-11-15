"""Thin, safe wrapper around the Groq chat API.

All agents talk to the model through one method: ``chat(system, user)``.
This gives us a single place to:
  * keep token usage low (reasoning effort, output caps), which matters on the free plan
  * fall back to a second model when the main one hits its rate limit
  * translate the many Groq SDK exceptions into our own friendly ``LLMError``
  * guard against empty responses
  * swap in a fake LLM for tests (anything with a matching ``chat`` method works)
"""

import logging
import re
from typing import Protocol

import groq

from .exceptions import LLMError
from .settings import Settings

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """Anything with this method can power the agents (real or fake)."""

    def chat(self, system: str, user: str, *, json_mode: bool = False, max_tokens: int | None = None) -> str: ...


def _is_capacity_error(e: Exception) -> bool:
    """Rate limit (429) or request too large for the plan's token limit (413)."""
    return isinstance(e, groq.RateLimitError) or (isinstance(e, groq.APIStatusError) and e.status_code == 413)


def _rate_limit_message(e: groq.APIStatusError, model: str) -> str:
    """Explain a 429/413 in plain words, using the details Groq sends back."""
    detail = str(getattr(e, "message", "") or e)
    wait = re.search(r"try again in ([\dhms.]+)", detail)
    wait_text = f" Try again in about {wait.group(1)}." if wait else " Please wait a minute and try again."
    if e.status_code == 413:
        return (f"The request was too large for your Groq plan's per-minute token limit on '{model}'. "
                "Try a shorter trip, or use a model with higher limits (GROQ_MODEL).")
    if "per day" in detail or "TPD" in detail or "RPD" in detail:
        return (f"Groq's daily limit for '{model}' has been reached.{wait_text} "
                "You can also switch to another model with GROQ_MODEL.")
    return f"Groq rate limit reached for '{model}'.{wait_text}"


class GroqLLM:
    """Real LLM client backed by the Groq API."""

    def __init__(self, settings: Settings, client: groq.Groq | None = None):
        self.model = settings.model
        self.fallback_model = settings.fallback_model if settings.fallback_model != settings.model else ""
        self.reasoning_effort = settings.reasoning_effort
        # The SDK itself retries rate limits, timeouts and 5xx errors with backoff
        # (it honours Groq's retry-after header for waits up to 60 seconds).
        self._client = client or groq.Groq(
            api_key=settings.api_key,
            timeout=settings.timeout,
            max_retries=settings.max_retries,
        )

    def chat(self, system: str, user: str, *, json_mode: bool = False, max_tokens: int | None = None) -> str:
        """Send one system + user message and return the reply text."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        try:
            return self._complete(self.model, messages, json_mode, max_tokens)
        except groq.APIStatusError as e:
            if not (_is_capacity_error(e) and self.fallback_model):
                raise self._translate(e, self.model) from e
            logger.warning("'%s' hit a rate/size limit; retrying on fallback '%s'.", self.model, self.fallback_model)
            try:
                return self._complete(self.fallback_model, messages, json_mode, max_tokens)
            except groq.GroqError as fallback_error:
                logger.warning("Fallback model failed too: %s", fallback_error)
                raise self._translate(e, self.model) from e  # report the original problem
        except groq.GroqError as e:
            raise self._translate(e, self.model) from e

    def _complete(self, model: str, messages: list[dict], json_mode: bool, max_tokens: int | None) -> str:
        """One raw API call. Raises raw groq errors (translated by ``chat``)."""
        kwargs: dict = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if max_tokens:
            kwargs["max_completion_tokens"] = max_tokens
        if model.startswith("openai/gpt-oss"):
            # Reasoning models spend hidden "thinking" tokens; "low" saves a lot of quota.
            kwargs["reasoning_effort"] = self.reasoning_effort

        response = self._client.chat.completions.create(model=model, messages=messages, **kwargs)
        if not response.choices:
            raise LLMError("The model returned no answer.")
        choice = response.choices[0]
        content = (choice.message.content or "").strip()
        if not content:
            if getattr(choice, "finish_reason", None) == "length":
                raise LLMError("The model ran out of output tokens before answering. Please try again.")
            raise LLMError("The model returned an empty answer.")
        if getattr(choice, "finish_reason", None) == "length":
            logger.warning("Reply from '%s' was cut off at the token limit.", model)
        return content

    def _translate(self, e: Exception, model: str) -> LLMError:
        """Map a Groq SDK exception to a friendly LLMError. Order matters (subclasses first)."""
        if isinstance(e, groq.AuthenticationError):
            return LLMError("Invalid Groq API key. Check GROQ_API_KEY in your .env file / Streamlit secrets.", fatal=True)
        if isinstance(e, groq.PermissionDeniedError):
            return LLMError("Your Groq API key does not have access to this model.", fatal=True)
        if isinstance(e, groq.NotFoundError):
            return LLMError(
                f"Model '{model}' not found. Check the current model names at "
                "https://console.groq.com/docs/models and set GROQ_MODEL.",
                fatal=True,
            )
        if _is_capacity_error(e):
            return LLMError(_rate_limit_message(e, model))
        if isinstance(e, groq.APITimeoutError):
            return LLMError("The request to Groq timed out. Please try again.")
        if isinstance(e, groq.APIConnectionError):
            return LLMError("Could not connect to Groq. Check your internet connection.")
        if isinstance(e, groq.BadRequestError):
            return LLMError(f"Groq rejected the request: {e.message}")
        if isinstance(e, groq.APIStatusError):
            return LLMError(f"Groq API error (HTTP {e.status_code}). Please try again later.")
        return LLMError(f"Unexpected Groq error: {e}")
