"""The Agent class and the team of travel workers.

Same idea as the class example: an agent is just a name + a role (system prompt)
+ a ``run(task, context)`` method. The difference is that the LLM is *injected*
instead of being a global, so tests can pass in a fake LLM.
"""

from dataclasses import dataclass

from .llm import LLMClient
from .prompts import REVIEWER, WORKER_SPECS, WorkerSpec


class Agent:
    """One worker: a role-specific system prompt in front of the LLM."""

    def __init__(self, spec: WorkerSpec, llm: LLMClient):
        self.key = spec.key
        self.name = spec.name
        self.description = spec.description
        self.system = f"You are the {spec.name}. {spec.role}"
        self.max_tokens = spec.max_tokens
        self._llm = llm

    def run(self, task: str, context: str = "") -> str:
        """Do one task, using the shared context produced so far."""
        prompt = f"Context:\n{context or '(none yet)'}\n\nTask: {task}"
        return self._llm.chat(self.system, prompt, max_tokens=self.max_tokens)

    def __repr__(self) -> str:
        return f"Agent({self.key!r})"


@dataclass
class Team:
    """The workers the planner can use, plus the reviewer (critic)."""

    workers: dict[str, Agent]
    reviewer: Agent

    def get(self, key: str) -> Agent | None:
        return self.workers.get(key)


def build_team(llm: LLMClient) -> Team:
    """Create every agent, all sharing one LLM client."""
    return Team(
        workers={spec.key: Agent(spec, llm) for spec in WORKER_SPECS},
        reviewer=Agent(REVIEWER, llm),
    )
