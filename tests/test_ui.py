"""Streamlit UI smoke tests using Streamlit's headless AppTest (fake LLM, no network)."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tests.conftest import FakeLLM

APP = str(Path(__file__).resolve().parent.parent / "ui" / "app.py")

PLAN = json.dumps({"steps": [{"worker": "researcher", "task": "research"}, {"worker": "writer", "task": "write"}]})


@pytest.fixture(autouse=True)
def fake_env(monkeypatch):
    # A real env var wins over .env, so the tests never use your real key.
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    fake = FakeLLM({
        "orchestrator": PLAN,
        "Destination Researcher": "Visit the Hagia Sophia.",
        "Itinerary Writer": "# My Istanbul Trip\n### Day 1",
        "Quality Reviewer": "APPROVED",
    })
    monkeypatch.setattr("travel_planner.orchestrator.GroqLLM", lambda settings: fake)


def test_app_renders_form():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert at.title[0].value == "✈️ Travel Planner Agent"
    assert at.text_input[0].label == "Destination *"


def test_empty_destination_shows_validation_error():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.button[0].click().run()
    assert not at.exception
    assert any("Destination is required" in e.value for e in at.error)


def test_full_run_shows_plan():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.text_input[0].input("Istanbul, Turkey")
    at.button[0].click().run()
    assert not at.exception
    assert not at.error
    assert any("My Istanbul Trip" in m.value for m in at.markdown)
    assert any("Approved" in s.value for s in at.success)


def test_missing_key_shows_friendly_error(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "paste_your_key_here")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert any("GROQ_API_KEY not found" in e.value for e in at.error)
