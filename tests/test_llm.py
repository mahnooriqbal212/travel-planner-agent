"""GroqLLM behaviour, tested with a mocked Groq client (no network)."""

from types import SimpleNamespace

import groq
import httpx
import pytest

from travel_planner.exceptions import ConfigError, LLMError
from travel_planner.llm import GroqLLM
from travel_planner.settings import Settings, load_settings

REQ = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
MAIN, FALLBACK = "openai/gpt-oss-120b", "llama-3.3-70b-versatile"


def status_error(cls, code, message="boom"):
    return cls(message, response=httpx.Response(code, request=REQ), body=None)


class FakeClient:
    """Mimics groq.Groq. ``behaviour`` maps model name -> Exception or reply text."""

    def __init__(self, behaviour: dict, finish_reason="stop"):
        self.behaviour = behaviour
        self.finish_reason = finish_reason
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        result = self.behaviour.get(kwargs["model"], "hello")
        if isinstance(result, Exception):
            raise result
        if result is None:
            return SimpleNamespace(choices=[])
        msg = SimpleNamespace(content=result)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason=self.finish_reason)])


def make(behaviour=None, fallback=FALLBACK, **client_kw):
    client = FakeClient(behaviour or {}, **client_kw)
    return GroqLLM(Settings(api_key="test", model=MAIN, fallback_model=fallback), client=client), client


def test_success_and_request_options():
    llm, client = make({MAIN: "  hi  "})
    assert llm.chat("s", "u", json_mode=True, max_tokens=500) == "hi"
    call = client.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    assert call["max_completion_tokens"] == 500
    assert call["reasoning_effort"] == "low"


def test_reasoning_effort_only_sent_to_gpt_oss():
    llm, client = make({MAIN: status_error(groq.RateLimitError, 429), FALLBACK: "ok"})
    assert llm.chat("s", "u") == "ok"
    assert "reasoning_effort" in client.calls[0] and "reasoning_effort" not in client.calls[1]


@pytest.mark.parametrize("error", [
    status_error(groq.RateLimitError, 429),
    status_error(groq.APIStatusError, 413, "Request too large"),
])
def test_capacity_errors_use_fallback_model(error):
    llm, client = make({MAIN: error, FALLBACK: "from fallback"})
    assert llm.chat("s", "u") == "from fallback"
    assert [c["model"] for c in client.calls] == [MAIN, FALLBACK]


def test_fallback_failure_reports_original_error():
    llm, _ = make({MAIN: status_error(groq.RateLimitError, 429), FALLBACK: status_error(groq.NotFoundError, 404)})
    with pytest.raises(LLMError) as exc:
        llm.chat("s", "u")
    assert "rate limit" in str(exc.value) and not exc.value.fatal


def test_no_fallback_when_disabled():
    llm, client = make({MAIN: status_error(groq.RateLimitError, 429)}, fallback="")
    with pytest.raises(LLMError):
        llm.chat("s", "u")
    assert len(client.calls) == 1


def test_other_errors_do_not_use_fallback():
    llm, client = make({MAIN: status_error(groq.AuthenticationError, 401)})
    with pytest.raises(LLMError) as exc:
        llm.chat("s", "u")
    assert exc.value.fatal and len(client.calls) == 1


def test_daily_limit_message_includes_wait_time():
    msg = "Rate limit reached on tokens per day (TPD): Limit 200000. Please try again in 7m12.5s."
    llm, _ = make({MAIN: status_error(groq.RateLimitError, 429, msg)}, fallback="")
    with pytest.raises(LLMError) as exc:
        llm.chat("s", "u")
    assert "daily limit" in str(exc.value) and "7m12.5s" in str(exc.value)


def test_413_message_is_explained():
    llm, _ = make({MAIN: status_error(groq.APIStatusError, 413)}, fallback="")
    with pytest.raises(LLMError) as exc:
        llm.chat("s", "u")
    assert "too large" in str(exc.value)


@pytest.mark.parametrize("error, fatal, text", [
    (status_error(groq.AuthenticationError, 401), True, "Invalid Groq API key"),
    (status_error(groq.NotFoundError, 404), True, "not found"),
    (status_error(groq.InternalServerError, 500), False, "HTTP 500"),
    (groq.APITimeoutError(request=REQ), False, "timed out"),
    (groq.APIConnectionError(request=REQ), False, "Could not connect"),
])
def test_errors_are_translated(error, fatal, text):
    llm, _ = make({MAIN: error})
    with pytest.raises(LLMError) as exc:
        llm.chat("s", "u")
    assert exc.value.fatal is fatal
    assert text in str(exc.value)


@pytest.mark.parametrize("content", ["", "   ", None])
def test_empty_reply_raises(content):
    llm, _ = make({MAIN: content})
    with pytest.raises(LLMError):
        llm.chat("s", "u")


def test_out_of_tokens_message():
    llm, _ = make({MAIN: ""}, finish_reason="length")
    with pytest.raises(LLMError) as exc:
        llm.chat("s", "u")
    assert "ran out of output tokens" in str(exc.value)


def test_settings_repr_hides_key():
    assert "secret123" not in repr(Settings(api_key="secret123"))


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.setattr("travel_planner.settings.load_dotenv", lambda: None)
    for name in ("GROQ_MODEL", "GROQ_FALLBACK_MODEL", "GROQ_REASONING_EFFORT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test")
    return monkeypatch


def test_missing_key_raises_config_error(clean_env):
    clean_env.setenv("GROQ_API_KEY", "paste_your_key_here")
    with pytest.raises(ConfigError):
        load_settings()


def test_fallback_can_be_disabled(clean_env):
    assert load_settings().fallback_model == FALLBACK
    clean_env.setenv("GROQ_FALLBACK_MODEL", "none")
    assert load_settings().fallback_model == ""


def test_invalid_reasoning_effort(clean_env):
    clean_env.setenv("GROQ_REASONING_EFFORT", "extreme")
    with pytest.raises(ConfigError):
        load_settings()
