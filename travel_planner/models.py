"""Data models: the user's trip request and the results the agents produce.

Validation and arithmetic (trip length, budget per day) are done here in plain
Python, not by the LLM. LLMs are bad at maths and can't be trusted to check
input, so we hand them facts we've already computed.
"""

from dataclasses import dataclass, field
from datetime import date

from .exceptions import TripValidationError

TRAVEL_STYLES = ("Budget", "Mid-range", "Luxury")
MAX_TRIP_DAYS = 21
MAX_TRAVELERS = 20
MAX_INTERESTS = 10


@dataclass
class TripRequest:
    """Everything the user tells us about the trip they want."""

    destination: str
    start_date: date
    end_date: date
    budget: float
    travelers: int = 1
    currency: str = "USD"
    origin: str = ""
    travel_style: str = "Mid-range"
    interests: list[str] = field(default_factory=list)
    notes: str = ""

    def __post_init__(self) -> None:
        # Normalise text first, then validate. Collect every error, not just the first.
        self.destination = (self.destination or "").strip()
        self.origin = (self.origin or "").strip()
        self.currency = (self.currency or "").strip().upper()
        self.notes = (self.notes or "").strip()
        self.interests = [i.strip() for i in (self.interests or []) if i and i.strip()]

        errors: list[str] = []
        if not self.destination:
            errors.append("Destination is required.")
        elif len(self.destination) > 100:
            errors.append("Destination must be 100 characters or fewer.")
        if len(self.origin) > 100:
            errors.append("Starting city must be 100 characters or fewer.")

        if not isinstance(self.start_date, date) or not isinstance(self.end_date, date):
            errors.append("Start and end dates are required.")
        elif self.end_date < self.start_date:
            errors.append("End date cannot be before the start date.")
        elif self.num_days > MAX_TRIP_DAYS:
            errors.append(f"Trips can be at most {MAX_TRIP_DAYS} days long.")

        if not isinstance(self.travelers, int) or not 1 <= self.travelers <= MAX_TRAVELERS:
            errors.append(f"Number of travelers must be between 1 and {MAX_TRAVELERS}.")
        if not isinstance(self.budget, (int, float)) or self.budget <= 0:
            errors.append("Budget must be greater than 0.")
        elif self.budget > 10_000_000:
            errors.append("Budget looks unrealistically large.")
        if len(self.currency) != 3 or not self.currency.isalpha():
            errors.append("Currency must be a 3-letter code such as USD, EUR or PKR.")
        if self.travel_style not in TRAVEL_STYLES:
            errors.append(f"Travel style must be one of: {', '.join(TRAVEL_STYLES)}.")
        if len(self.interests) > MAX_INTERESTS:
            errors.append(f"Choose at most {MAX_INTERESTS} interests.")
        if any(len(i) > 40 for i in self.interests):
            errors.append("Each interest must be 40 characters or fewer.")
        if len(self.notes) > 500:
            errors.append("Notes must be 500 characters or fewer.")

        if errors:
            raise TripValidationError(errors)

    # ---- facts computed in Python (the LLM receives them ready-made) ----
    @property
    def num_days(self) -> int:
        return (self.end_date - self.start_date).days + 1

    @property
    def num_nights(self) -> int:
        return self.num_days - 1

    @property
    def budget_per_day(self) -> float:
        return self.budget / self.num_days

    @property
    def budget_per_person_per_day(self) -> float:
        return self.budget / self.num_days / self.travelers

    def to_prompt(self) -> str:
        """Describe the trip as text that every agent receives as context."""
        lines = [
            f"Destination: {self.destination}",
            f"Travelling from: {self.origin or 'not specified'}",
            f"Dates: {self.start_date:%A %d %B %Y} to {self.end_date:%A %d %B %Y} "
            f"({self.num_days} days, {self.num_nights} nights)",
            f"Travelers: {self.travelers}",
            f"Total budget: {self.budget:,.0f} {self.currency} "
            f"(about {self.budget_per_day:,.0f} {self.currency} per day, "
            f"{self.budget_per_person_per_day:,.0f} {self.currency} per person per day)",
            f"Travel style: {self.travel_style}",
            f"Interests: {', '.join(self.interests) if self.interests else 'general sightseeing'}",
        ]
        if self.notes:
            lines.append(f"Special requests: {self.notes}")
        return "\n".join(lines)


# ---------------------------------------------------------------- results ----
@dataclass
class Step:
    """One planned task: which worker should do what."""

    worker: str
    task: str


@dataclass
class StepResult:
    """What happened when a worker ran its step."""

    worker: str
    worker_name: str
    task: str
    output: str = ""
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class ReviewRound:
    """One pass of the reviewer's critique."""

    round: int
    feedback: str
    approved: bool


@dataclass
class TripPlanResult:
    """The full outcome of one orchestrator run."""

    request: TripRequest
    final_plan: str
    steps: list[StepResult] = field(default_factory=list)
    reviews: list[ReviewRound] = field(default_factory=list)
    used_fallback_plan: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def approved(self) -> bool:
        return bool(self.reviews) and self.reviews[-1].approved

    def outputs_by_worker(self) -> dict[str, list[StepResult]]:
        """Group successful step outputs by worker key (handy for UI tabs)."""
        grouped: dict[str, list[StepResult]] = {}
        for step in self.steps:
            if step.ok:
                grouped.setdefault(step.worker, []).append(step)
        return grouped
