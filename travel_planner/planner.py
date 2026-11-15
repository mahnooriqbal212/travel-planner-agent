"""The planning step: ask the LLM to split the goal into worker steps.

LLM output is untrusted, so this module defends against every way it can go wrong:
  * invalid / non-JSON reply          -> extract JSON from the text, else fall back
  * JSON mode rejected by the API     -> retry once without JSON mode
  * unknown worker names, empty tasks -> skip those steps
  * too many steps                    -> truncate to max_steps
  * last step isn't the writer        -> append a writer step
  * nothing usable at all             -> use a sensible default plan
"""

import json
import logging
import re
from dataclasses import dataclass

from .exceptions import LLMError
from .llm import LLMClient
from .models import Step
from .prompts import FINAL_WORKER, PLANNER_MAX_TOKENS, WORKER_SPECS, planner_prompt

logger = logging.getLogger(__name__)

MAX_TASK_CHARS = 600
FINAL_TASK = "Write the complete final travel plan using all the information in the context."


@dataclass
class PlanResult:
    steps: list[Step]
    used_fallback: bool = False


def default_plan(destination: str) -> list[Step]:
    """Plan used when the LLM's plan is unusable. Covers every worker once."""
    return [
        Step("researcher", f"Research {destination}: attractions matching the interests, food, weather, etiquette and tips."),
        Step("logistics", f"Plan how to get to and around {destination} and the best areas to stay."),
        Step("budget", f"Estimate the full trip cost for {destination} and check it against the budget."),
        Step(FINAL_WORKER, FINAL_TASK),
    ]


def extract_json(text: str) -> dict | None:
    """Parse a JSON object from LLM text, tolerating ```json fences or extra prose."""
    if not text:
        return None
    candidates = [text.strip()]
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        candidates.append(fenced.group(1))
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict):
            return data
    return None


class Planner:
    def __init__(self, llm: LLMClient, valid_workers: set[str], max_steps: int = 8):
        self._llm = llm
        self._valid = valid_workers
        self._max_steps = max_steps
        self._system = planner_prompt(
            tuple(s for s in WORKER_SPECS if s.key in valid_workers), max_steps
        )

    def plan(self, goal: str, destination: str) -> PlanResult:
        """Return validated steps. Only fatal LLM errors (e.g. bad API key) escape."""
        steps: list[Step] = []
        try:
            steps = self.parse_steps(self._ask(goal))
        except LLMError as e:
            if e.fatal:
                raise
            logger.warning("Planner call failed, using default plan: %s", e)

        if not steps:
            logger.warning("Planner produced no usable steps; using default plan.")
            return PlanResult(default_plan(destination), used_fallback=True)
        return PlanResult(steps)

    def _ask(self, goal: str) -> str:
        try:
            return self._llm.chat(self._system, goal, json_mode=True, max_tokens=PLANNER_MAX_TOKENS)
        except LLMError as e:
            if e.fatal:
                raise
            # Some models/providers reject JSON mode; ask again as plain text.
            logger.info("JSON-mode planning failed (%s); retrying without JSON mode.", e)
            return self._llm.chat(self._system, goal, max_tokens=PLANNER_MAX_TOKENS)

    def parse_steps(self, raw: str) -> list[Step]:
        """Turn the raw LLM reply into a clean list of Steps (may be empty)."""
        data = extract_json(raw)
        if data is None:
            logger.warning("Planner reply was not valid JSON: %.200s", raw)
            return []
        raw_steps = data.get("steps")
        if not isinstance(raw_steps, list):
            logger.warning("Planner JSON has no 'steps' list.")
            return []

        steps: list[Step] = []
        for item in raw_steps:
            if not isinstance(item, dict):
                continue
            worker = str(item.get("worker", "")).strip().lower()
            task = str(item.get("task", "")).strip()
            if worker not in self._valid:
                logger.warning("Skipping step for unknown worker %r.", worker)
                continue
            if not task:
                continue
            steps.append(Step(worker, task[:MAX_TASK_CHARS]))

        if not steps:
            return []
        # Guarantee the writer is last, then cap the length (always keeping the writer).
        if steps[-1].worker != FINAL_WORKER:
            steps.append(Step(FINAL_WORKER, FINAL_TASK))
        if len(steps) > self._max_steps:
            steps = steps[: self._max_steps - 1] + [steps[-1]]
        return steps
