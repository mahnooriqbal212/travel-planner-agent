"""Command-line interface for the travel planner.

Run:  python main.py
"""

import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from travel_planner import (
    TRAVEL_STYLES,
    Event,
    EventType,
    TravelPlannerError,
    TripRequest,
    TripValidationError,
    create_orchestrator,
)
from travel_planner.export import safe_filename, to_markdown

ICONS = {
    EventType.PLAN_READY: "🗺️ ",
    EventType.STEP_STARTED: "-->",
    EventType.STEP_DONE: "  ✓",
    EventType.STEP_FAILED: "  ✗",
    EventType.REVIEW: "🔍",
    EventType.REVISION: "✏️ ",
    EventType.WARNING: "⚠️ ",
    EventType.DONE: "✅",
}


def print_event(event: Event) -> None:
    print(f"{ICONS.get(event.type, '-')} {event.message}")
    if event.type is EventType.PLAN_READY:
        for i, (worker, task) in enumerate(event.data, start=1):
            print(f"     {i}. [{worker}] {task}")


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    return input(f"{prompt}{suffix}: ").strip() or default


def ask_date(prompt: str, default: date) -> date:
    while True:
        raw = ask(prompt + " (YYYY-MM-DD)", default.isoformat())
        try:
            return date.fromisoformat(raw)
        except ValueError:
            print("  Please use the format YYYY-MM-DD.")


def ask_number(prompt: str, default: float, cast=float):
    while True:
        raw = ask(prompt, str(default))
        try:
            return cast(raw.replace(",", ""))
        except ValueError:
            print("  Please enter a number.")


def collect_request() -> TripRequest:
    """Ask questions until the trip details pass validation."""
    print("\n=== ✈️  Travel Planner Agent ===\n")
    while True:
        destination = ask("Destination (e.g. Istanbul, Turkey)")
        origin = ask("Travelling from (optional)")
        start = ask_date("Start date", date.today() + timedelta(days=30))
        try:
            return TripRequest(
                destination=destination,
                origin=origin,
                start_date=start,
                end_date=ask_date("End date", start + timedelta(days=3)),
                travelers=ask_number("Number of travelers", 1, int),
                budget=ask_number("Total budget", 1500.0),
                currency=ask("Currency", "USD"),
                travel_style=ask(f"Travel style {TRAVEL_STYLES}", "Mid-range"),
                interests=[i for i in ask("Interests (comma separated)", "food, history").split(",")],
                notes=ask("Special requests (optional)"),
            )
        except TripValidationError as e:
            print("\n❌ Please fix these and try again:")
            for err in e.errors:
                print(f"   - {err}")
            print()


def use_utf8_console() -> None:
    """Windows consoles often default to cp1252, which can't print emoji or the
    special characters LLMs like to use. Switch to UTF-8 and replace anything
    that still can't be shown, instead of crashing."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main() -> int:
    use_utf8_console()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    try:
        request = collect_request()
        orchestrator = create_orchestrator(on_event=print_event)
        print()
        result = orchestrator.run(request)
    except (KeyboardInterrupt, EOFError):  # Ctrl+C, or input closed (Ctrl+Z / Ctrl+D)
        print("\nCancelled.")
        return 130
    except TravelPlannerError as e:  # config, API, or planning problems
        print(f"\n❌ {e}")
        return 1
    except Exception:  # last-resort safety net: log details, show a short message
        logging.exception("Unexpected error")
        print("\n❌ Something unexpected went wrong. See the error above.")
        return 1

    print("\n" + "=" * 70 + "\n")
    print(result.final_plan)
    try:
        out_dir = Path("output")
        out_dir.mkdir(exist_ok=True)
        path = out_dir / safe_filename(result)
        path.write_text(to_markdown(result), encoding="utf-8")
        print(f"\n💾 Saved to {path}")
    except OSError as e:
        print(f"\n⚠️  Could not save the plan to a file: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
