"""GroqLLM error translation, tested with a mocked Groq client (no network)."""

from types import SimpleNamespace

import groq
import httpx
import pytest

from travel_planner.exceptions import ConfigError, LLMError
from travel_planner.llm import GroqLLM
from travel_planner.settings import Settings, load_settings

REQ = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def status_error(cls, code):
    return cls("boom", response=httpx.Response(code, request=REQ), body=None)


def fake_client(*, raises=None, content="hello"):
    def create(**kwargs):
        fake_client.last_kwargs = kwargs
        if raises:
            raise raises
        msg = SimpleNamespace(content=content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)] if content is not None else [])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def llm(**kw):
    return GroqLLM(Settings(api_key="test"), client=fake_client(**kw))


def test_success_and_json_mode():
    assert llm(content="  hi  ").chat("s", "u") == "hi"
    llm().chat("s", "u", json_mode=True)
    assert fake_client.last_kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("error, fatal, text", [
    (status_error(groq.AuthenticationError, 401), True, "Invalid Groq API key"),
    (status_error(groq.NotFoundError, 404), True, "not found"),
    (status_error(groq.RateLimitError, 429), False, "rate limit"),
    (status_error(groq.InternalServerError, 500), False, "HTTP 500"),
    (groq.APITimeoutError(request=REQ), False, "timed out"),
    (groq.APIConnectionError(request=REQ), False, "Could not connect"),
])
def test_errors_are_translated(error, fatal, text):
    with pytest.raises(LLMError) as exc:
        llm(raises=error).chat("s", "u")
    assert exc.value.fatal is fatal
    assert text in str(exc.value)


@pytest.mark.parametrize("content", ["", "   ", None])
def test_empty_reply_raises(content):
    with pytest.raises(LLMError):
        llm(content=content).chat("s", "u")


def test_settings_repr_hides_key():
    assert "secret123" not in repr(Settings(api_key="secret123"))


def test_missing_key_raises_config_error(monkeypatch):
    monkeypatch.setattr("travel_planner.settings.load_dotenv", lambda: None)
    monkeypatch.setenv("GROQ_API_KEY", "paste_your_key_here")
    with pytest.raises(ConfigError):
        load_settings()
