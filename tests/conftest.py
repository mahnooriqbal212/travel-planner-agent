"""Shared test fixtures. Tests never call the real API: they use FakeLLM."""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from travel_planner.models import TripRequest  # noqa: E402


class FakeLLM:
    """Scripted LLM. ``routes`` maps a substring of the system prompt to the reply.

    A reply may be a string, an Exception (raised), or a list of those
    (consumed one per call; the last item repeats).
    """

    def __init__(self, routes: dict):
        self.routes = routes
        self.calls: list[dict] = []

    def chat(self, system: str, user: str, *, json_mode: bool = False) -> str:
        self.calls.append({"system": system, "user": user, "json_mode": json_mode})
        for key, reply in self.routes.items():
            if key in system:
                if isinstance(reply, list):
                    reply = reply.pop(0) if len(reply) > 1 else reply[0]
                if isinstance(reply, Exception):
                    raise reply
                return reply
        return f"default reply for: {system[:30]}"

    def calls_to(self, key: str) -> list[dict]:
        return [c for c in self.calls if key in c["system"]]


@pytest.fixture
def trip() -> TripRequest:
    return TripRequest(
        destination="Istanbul, Turkey",
        origin="Lahore",
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 4),
        budget=2000,
        travelers=2,
        currency="usd",
        interests=["Food", "History"],
    )
