import json

import pytest

from travel_planner.exceptions import LLMError
from travel_planner.planner import Planner, extract_json
from tests.conftest import FakeLLM

VALID = {"researcher", "logistics", "budget", "writer"}


def plan_json(*steps):
    return json.dumps({"steps": [{"worker": w, "task": t} for w, t in steps]})


def make_planner(reply, max_steps=8):
    llm = FakeLLM({"orchestrator": reply})
    return Planner(llm, VALID, max_steps), llm


def test_valid_plan_is_used():
    planner, llm = make_planner(plan_json(("researcher", "find"), ("budget", "cost"), ("writer", "write")))
    result = planner.plan("goal", "Paris")
    assert not result.used_fallback
    assert [s.worker for s in result.steps] == ["researcher", "budget", "writer"]
    assert llm.calls[0]["json_mode"] is True


def test_writer_appended_when_missing():
    planner, _ = make_planner(plan_json(("researcher", "find")))
    assert [s.worker for s in planner.plan("g", "Paris").steps] == ["researcher", "writer"]


def test_unknown_workers_and_empty_tasks_skipped():
    planner, _ = make_planner(plan_json(("hacker", "x"), ("researcher", ""), (" Budget ", "cost"), ("writer", "w")))
    assert [s.worker for s in planner.plan("g", "Paris").steps] == ["budget", "writer"]


def test_too_many_steps_truncated_but_writer_kept():
    steps = [("researcher", f"t{i}") for i in range(10)] + [("writer", "final")]
    planner, _ = make_planner(plan_json(*steps), max_steps=4)
    result = planner.plan("g", "Paris").steps
    assert len(result) == 4 and result[-1].worker == "writer" and result[-1].task == "final"


@pytest.mark.parametrize("reply", ["not json at all", '{"steps": "nope"}', '{"steps": []}', "[1, 2]"])
def test_bad_replies_fall_back_to_default(reply):
    planner, _ = make_planner(reply)
    result = planner.plan("g", "Paris")
    assert result.used_fallback
    assert [s.worker for s in result.steps] == ["researcher", "logistics", "budget", "writer"]
    assert "Paris" in result.steps[0].task


def test_json_mode_failure_retries_without_json_mode():
    good = plan_json(("researcher", "find"), ("writer", "w"))
    planner, llm = make_planner([LLMError("json mode unsupported"), good])
    result = planner.plan("g", "Paris")
    assert not result.used_fallback
    assert [c["json_mode"] for c in llm.calls] == [True, False]


def test_non_fatal_llm_error_falls_back():
    planner, _ = make_planner(LLMError("rate limited"))
    assert planner.plan("g", "Paris").used_fallback


def test_fatal_llm_error_propagates():
    planner, _ = make_planner(LLMError("bad key", fatal=True))
    with pytest.raises(LLMError):
        planner.plan("g", "Paris")


def test_extract_json_handles_fences_and_prose():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! Here it is: {"a": 2} hope it helps') == {"a": 2}
    assert extract_json("") is None
    assert extract_json("{broken") is None
