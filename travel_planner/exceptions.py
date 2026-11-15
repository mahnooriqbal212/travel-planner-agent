"""Custom exceptions for the travel planner.

Every error raised on purpose by this package inherits from ``TravelPlannerError``,
so callers (the CLI, the Streamlit UI) can catch one base class and show a
friendly message instead of crashing with a raw traceback.
"""


class TravelPlannerError(Exception):
    """Base class for all travel planner errors."""


class ConfigError(TravelPlannerError):
    """Missing or invalid configuration (e.g. no API key)."""


class TripValidationError(TravelPlannerError):
    """The user's trip details are invalid.

    ``errors`` holds every problem found, so the UI can show them all at once.
    """

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("Invalid trip details:\n- " + "\n- ".join(errors))


class LLMError(TravelPlannerError):
    """A call to the language model failed.

    ``fatal=True`` means retrying is pointless (bad API key, unknown model),
    so the orchestrator should stop instead of moving on to the next step.
    """

    def __init__(self, message: str, *, fatal: bool = False):
        self.fatal = fatal
        super().__init__(message)


class PlanningError(TravelPlannerError):
    """The agents could not produce a final travel plan."""
