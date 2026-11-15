"""Thin, safe wrapper around the Groq chat API.

All agents talk to the model through one method: ``chat(system, user)``.
This gives us a single place to:
  * translate the many Groq SDK exceptions into our own friendly ``LLMError``
  * guard against empty responses
  * swap in a fake LLM for tests (anything with a matching ``chat`` method works)
"""

import logging
from typing import Protocol

import groq

from .exceptions import LLMError
from .settings import Settings

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """Anything with this method can power the agents (real or fake)."""

    def chat(self, system: str, user: str, *, json_mode: bool = False) -> str: ...


class GroqLLM:
    """Real LLM client backed by the Groq API."""

    def __init__(self, settings: Settings, client: groq.Groq | None = None):
        self.model = settings.model
        # The SDK itself retries rate limits, timeouts and 5xx errors with backoff.
        self._client = client or groq.Groq(
            api_key=settings.api_key,
            timeout=settings.timeout,
            max_retries=settings.max_retries,
        )

    def chat(self, system: str, user: str, *, json_mode: bool = False) -> str:
        """Send one system + user message and return the reply text."""
        kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                **kwargs,
            )
        # Order matters: subclasses must be caught before their parents.
        except groq.AuthenticationError as e:
            raise LLMError("Invalid Groq API key. Check GROQ_API_KEY in your .env file.", fatal=True) from e
        except groq.PermissionDeniedError as e:
            raise LLMError("Your Groq API key does not have access to this model.", fatal=True) from e
        except groq.NotFoundError as e:
            raise LLMError(
                f"Model '{self.model}' not found. Check the current model names at "
                "https://console.groq.com/docs/models and set GROQ_MODEL.",
                fatal=True,
            ) from e
        except groq.RateLimitError as e:
            raise LLMError("Groq rate limit reached. Please wait a minute and try again.") from e
        except groq.APITimeoutError as e:
            raise LLMError("The request to Groq timed out. Please try again.") from e
        except groq.APIConnectionError as e:
            raise LLMError("Could not connect to Groq. Check your internet connection.") from e
        except groq.BadRequestError as e:
            raise LLMError(f"Groq rejected the request: {e.message}") from e
        except groq.APIStatusError as e:
            raise LLMError(f"Groq API error (HTTP {e.status_code}). Please try again later.") from e
        except groq.GroqError as e:
            raise LLMError(f"Unexpected Groq error: {e}") from e

        if not response.choices:
            raise LLMError("The model returned no answer.")
        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise LLMError("The model returned an empty answer.")
        return content
