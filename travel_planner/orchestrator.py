"""The orchestrator: plan -> delegate to workers -> review/fix loop.

This is the same pattern as ``orchestrate()`` in the class example, made robust:
  * a failing worker doesn't crash the run; its error is recorded and the
    other workers carry on (the writer works with whatever context exists)
  * fatal errors (bad API key, unknown model) stop the run immediately
  * if the reviewer or a fix attempt fails, we keep the last good draft
  * progress is reported through an ``on_event`` callback instead of print(),
    so the same core logic can drive the CLI *and* the Streamlit UI
"""

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .agents import Team, build_team
from .exceptions import LLMError, PlanningError
from .llm import GroqLLM, LLMClient
from .models import ReviewRound, StepResult, TripPlanResult, TripRequest
from .planner import FINAL_TASK, Planner
from .prompts import FINAL_WORKER
from .settings import Settings, load_settings

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    PLAN_READY = "plan_ready"
    STEP_STARTED = "step_started"
    STEP_DONE = "step_done"
    STEP_FAILED = "step_failed"
    REVIEW = "review"
    REVISION = "revision"
    WARNING = "warning"
    DONE = "done"


@dataclass
class Event:
    type: EventType
    message: str
    data: Any = None


EventHandler = Callable[[Event], None]


def is_approved(review: str) -> bool:
    """True if the reviewer approved, tolerating markdown like '**APPROVED**'."""
    cleaned = re.sub(r"[^A-Za-z]", " ", review).strip().upper()
    return cleaned.startswith("APPROVED")


class TravelPlannerOrchestrator:
    def __init__(
        self,
        llm: LLMClient,
        *,
        max_revisions: int = 2,
        max_steps: int = 8,
        on_event: EventHandler | None = None,
    ):
        self.team: Team = build_team(llm)
        self.planner = Planner(llm, set(self.team.workers), max_steps)
        self.max_revisions = max_revisions
        self._on_event = on_event

    # ------------------------------------------------------------ helpers --
    def _emit(self, type_: EventType, message: str, data: Any = None) -> None:
        logger.info("%s: %s", type_.value, message)
        if self._on_event is None:
            return
        try:
            self._on_event(Event(type_, message, data))
        except Exception:  # a broken UI callback must never break planning
            logger.exception("on_event handler raised; ignoring.")

    def _warn(self, result_warnings: list[str], message: str) -> None:
        result_warnings.append(message)
        self._emit(EventType.WARNING, message)

    # --------------------------------------------------------------- main --
    def run(self, request: TripRequest) -> TripPlanResult:
        """Produce a travel plan. Raises LLMError (fatal) or PlanningError."""
        goal = request.to_prompt()
        warnings: list[str] = []

        # 1. Plan
        plan = self.planner.plan(goal, request.destination)
        if plan.used_fallback:
            self._warn(warnings, "The planner's reply was unusable, so a default plan was used.")
        self._emit(
            EventType.PLAN_READY,
            f"Plan ready with {len(plan.steps)} steps.",
            [(s.worker, s.task) for s in plan.steps],
        )

        # 2. Delegate each step; the context is the team's shared memory.
        context = f"[Trip Request]\n{goal}"
        results: list[StepResult] = []
        for i, step in enumerate(plan.steps, start=1):
            agent = self.team.get(step.worker)
            self._emit(EventType.STEP_STARTED, f"Step {i}/{len(plan.steps)}: {agent.name}: {step.task}",
                       {"index": i, "worker": agent.key})
            result = StepResult(step.worker, agent.name, step.task)
            try:
                result.output = agent.run(step.task, context)
                context += f"\n\n[{agent.name}]\n{result.output}"
                self._emit(EventType.STEP_DONE, f"{agent.name} finished.", {"index": i, "worker": agent.key})
            except LLMError as e:
                if e.fatal:
                    raise
                result.error = str(e)
                self._emit(EventType.STEP_FAILED, f"{agent.name} failed: {e}", {"index": i, "worker": agent.key})
                self._warn(warnings, f"{agent.name} step failed ({e}); the plan may be less detailed.")
            results.append(result)

        # 3. The draft is the writer's final output. Retry once if it failed.
        draft = results[-1].output if results and results[-1].ok else ""
        if not draft:
            draft = self._retry_writer(context, results)

        # 4. Critic loop: reviewer checks, writer fixes.
        reviews: list[ReviewRound] = []
        for round_no in range(1, self.max_revisions + 1):
            try:
                feedback = self.team.reviewer.run(
                    "Review this travel plan against the trip request.",
                    f"[Trip Request]\n{goal}\n\n[Draft Plan]\n{draft}",
                )
            except LLMError as e:
                if e.fatal:
                    raise
                self._warn(warnings, f"Review skipped ({e}). Showing the unreviewed plan.")
                break

            approved = is_approved(feedback)
            reviews.append(ReviewRound(round_no, feedback, approved))
            self._emit(EventType.REVIEW, "Reviewer approved the plan." if approved
                       else f"Reviewer requested changes (round {round_no}).", feedback)
            if approved:
                break

            try:
                draft = self.team.workers[FINAL_WORKER].run(
                    f"Revise the travel plan to fix these issues:\n{feedback}\n\n"
                    "Return the complete revised plan, not just the changes.",
                    f"[Trip Request]\n{goal}\n\n[Research]\n{context}\n\n[Current Draft]\n{draft}",
                )
                self._emit(EventType.REVISION, f"Writer revised the plan (round {round_no}).")
            except LLMError as e:
                if e.fatal:
                    raise
                self._warn(warnings, f"Revision failed ({e}). Keeping the previous draft.")
                break

        if reviews and not reviews[-1].approved and len(reviews) == self.max_revisions:
            self._warn(warnings, "The reviewer still had suggestions after the final revision round.")

        self._emit(EventType.DONE, "Travel plan complete.")
        return TripPlanResult(
            request=request,
            final_plan=draft,
            steps=results,
            reviews=reviews,
            used_fallback_plan=plan.used_fallback,
            warnings=warnings,
        )

    def _retry_writer(self, context: str, results: list[StepResult]) -> str:
        writer = self.team.workers[FINAL_WORKER]
        if not any(r.ok for r in results):
            raise PlanningError("Every agent failed, so no plan could be created. Please try again.")
        self._emit(EventType.WARNING, "Retrying the Itinerary Writer.")
        try:
            output = writer.run(FINAL_TASK, context)
        except LLMError as e:
            if e.fatal:
                raise
            raise PlanningError(f"Could not write the final plan: {e}") from e
        results.append(StepResult(FINAL_WORKER, writer.name, FINAL_TASK, output))
        return output


def create_orchestrator(
    on_event: EventHandler | None = None,
    settings: Settings | None = None,
    llm: LLMClient | None = None,
) -> TravelPlannerOrchestrator:
    """Convenience factory: load settings and wire up the real Groq LLM.

    Raises ConfigError if the API key is missing.
    """
    settings = settings or load_settings()
    return TravelPlannerOrchestrator(
        llm or GroqLLM(settings),
        max_revisions=settings.max_revisions,
        max_steps=settings.max_steps,
        on_event=on_event,
    )
