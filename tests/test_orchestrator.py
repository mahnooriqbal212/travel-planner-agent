import json

import pytest

from travel_planner.exceptions import LLMError, PlanningError
from travel_planner.orchestrator import EventType, TravelPlannerOrchestrator, is_approved
from tests.conftest import FakeLLM

PLAN = json.dumps({"steps": [
    {"worker": "researcher", "task": "research"},
    {"worker": "budget", "task": "budget"},
    {"worker": "writer", "task": "write"},
]})


def routes(**overrides):
    base = {
        "orchestrator": PLAN,
        "Destination Researcher": "research notes",
        "Budget Analyst": "budget table",
        "Itinerary Writer": "DRAFT v1",
        "Quality Reviewer": "APPROVED",
    }
    base.update(overrides)
    return base


def run(trip, llm, **kwargs):
    events = []
    orch = TravelPlannerOrchestrator(llm, on_event=events.append, **kwargs)
    return orch.run(trip), events


def test_happy_path(trip):
    llm = FakeLLM(routes())
    result, events = run(trip, llm)
    assert result.final_plan == "DRAFT v1"
    assert result.approved and len(result.reviews) == 1
    assert [s.worker for s in result.steps] == ["researcher", "budget", "writer"]
    assert result.warnings == []
    assert events[0].type is EventType.PLAN_READY and events[-1].type is EventType.DONE


def test_context_is_shared_between_workers(trip):
    llm = FakeLLM(routes())
    run(trip, llm)
    writer_prompt = llm.calls_to("Itinerary Writer")[0]["user"]
    assert "Istanbul" in writer_prompt  # trip request always included
    assert "research notes" in writer_prompt and "budget table" in writer_prompt
    reviewer_prompt = llm.calls_to("Quality Reviewer")[0]["user"]
    assert "Istanbul" in reviewer_prompt and "DRAFT v1" in reviewer_prompt


def test_revision_loop_until_approved(trip):
    llm = FakeLLM(routes(**{
        "Itinerary Writer": ["DRAFT v1", "DRAFT v2"],
        "Quality Reviewer": ["1. Add day 4", "**APPROVED**"],
    }))
    result, _ = run(trip, llm)
    assert result.final_plan == "DRAFT v2"
    assert [r.approved for r in result.reviews] == [False, True]
    # The revision request carries the draft + feedback, not the full research (keeps it small).
    revision_prompt = llm.calls_to("Itinerary Writer")[1]["user"]
    assert "DRAFT v1" in revision_prompt and "Add day 4" in revision_prompt
    assert "research notes" not in revision_prompt


def test_stops_after_max_revisions(trip):
    llm = FakeLLM(routes(**{"Quality Reviewer": "1. fix things"}))
    result, _ = run(trip, llm, max_revisions=2)
    assert len(result.reviews) == 2 and not result.approved
    assert any("still had suggestions" in w for w in result.warnings)


def test_zero_revisions_skips_review(trip):
    llm = FakeLLM(routes())
    result, _ = run(trip, llm, max_revisions=0)
    assert result.reviews == [] and not llm.calls_to("Quality Reviewer")


def test_failed_worker_does_not_stop_run(trip):
    llm = FakeLLM(routes(**{"Budget Analyst": LLMError("timeout")}))
    result, events = run(trip, llm)
    assert result.final_plan == "DRAFT v1"
    assert not result.steps[1].ok and "timeout" in result.steps[1].error
    assert any("Budget Analyst" in w for w in result.warnings)
    assert any(e.type is EventType.STEP_FAILED for e in events)


def test_writer_failure_is_retried(trip):
    llm = FakeLLM(routes(**{"Itinerary Writer": [LLMError("blip"), "DRAFT retry"]}))
    result, _ = run(trip, llm)
    assert result.final_plan == "DRAFT retry"


def test_writer_failing_twice_raises_planning_error(trip):
    llm = FakeLLM(routes(**{"Itinerary Writer": LLMError("down")}))
    with pytest.raises(PlanningError):
        run(trip, llm)


def test_all_workers_failing_raises_planning_error(trip):
    err = LLMError("down")
    llm = FakeLLM(routes(**{"Destination Researcher": err, "Budget Analyst": err, "Itinerary Writer": err}))
    with pytest.raises(PlanningError):
        run(trip, llm)


def test_fatal_error_stops_immediately(trip):
    llm = FakeLLM(routes(**{"Destination Researcher": LLMError("bad key", fatal=True)}))
    with pytest.raises(LLMError):
        run(trip, llm)
    assert not llm.calls_to("Budget Analyst")


def test_reviewer_failure_keeps_draft(trip):
    llm = FakeLLM(routes(**{"Quality Reviewer": LLMError("rate limit")}))
    result, _ = run(trip, llm)
    assert result.final_plan == "DRAFT v1" and result.reviews == []
    assert any("Review skipped" in w for w in result.warnings)


def test_broken_event_handler_does_not_crash(trip):
    def bad_handler(event):
        raise RuntimeError("UI bug")
    orch = TravelPlannerOrchestrator(FakeLLM(routes()), on_event=bad_handler)
    assert orch.run(trip).final_plan == "DRAFT v1"


def test_fallback_plan_warns(trip):
    result, _ = run(trip, FakeLLM(routes(orchestrator="garbage")))
    assert result.used_fallback_plan
    assert [s.worker for s in result.steps] == ["researcher", "logistics", "budget", "writer"]


@pytest.mark.parametrize("text, expected", [
    ("APPROVED", True), ("**APPROVED**", True), ("approved.", True),
    ("1. Not approved yet", False), ("NOT APPROVED", False), ("", False),
])
def test_is_approved(text, expected):
    assert is_approved(text) is expected
