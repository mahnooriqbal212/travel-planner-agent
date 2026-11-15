"""Reusable Streamlit widgets. Only UI code lives here; all planning logic is
imported from the ``travel_planner`` package."""

from datetime import date, timedelta

import streamlit as st

from travel_planner import TRAVEL_STYLES, Event, EventType, TripPlanResult, TripRequest, TripValidationError
from travel_planner.export import safe_filename, to_markdown
from travel_planner.models import MAX_TRAVELERS, MAX_TRIP_DAYS

INTEREST_OPTIONS = [
    "Food", "History", "Culture", "Nature", "Beaches", "Adventure", "Shopping",
    "Nightlife", "Museums", "Architecture", "Photography", "Family-friendly", "Relaxation",
]
CURRENCIES = ["USD", "EUR", "GBP", "PKR", "AED", "SAR", "INR", "TRY", "JPY", "CAD", "AUD"]

TAB_LABELS = {
    "researcher": "🔎 Research",
    "logistics": "🚆 Logistics & stay",
    "budget": "💰 Budget",
}

EVENT_ICONS = {
    EventType.PLAN_READY: "🗺️",
    EventType.STEP_STARTED: "⏳",
    EventType.STEP_DONE: "✅",
    EventType.STEP_FAILED: "❌",
    EventType.REVIEW: "🔍",
    EventType.REVISION: "✏️",
    EventType.WARNING: "⚠️",
    EventType.DONE: "🎉",
}


def trip_form() -> TripRequest | None:
    """Render the trip form. Returns a valid TripRequest once submitted, else None."""
    today = date.today()
    with st.form("trip_form"):
        st.subheader("Where are you going?")
        c1, c2 = st.columns(2)
        destination = c1.text_input("Destination *", placeholder="e.g. Istanbul, Turkey", max_chars=100)
        origin = c2.text_input("Travelling from", placeholder="e.g. Lahore, Pakistan", max_chars=100)

        c1, c2, c3 = st.columns(3)
        start = c1.date_input("Start date *", value=today + timedelta(days=30), min_value=today)
        end = c2.date_input("End date *", value=today + timedelta(days=33), min_value=today)
        travelers = c3.number_input("Travelers *", min_value=1, max_value=MAX_TRAVELERS, value=1, step=1)

        c1, c2, c3 = st.columns(3)
        budget = c1.number_input("Total budget *", min_value=0.0, value=1500.0, step=100.0, format="%.0f")
        currency = c2.selectbox("Currency", CURRENCIES, index=0)
        style = c3.selectbox("Travel style", TRAVEL_STYLES, index=1)

        interests = st.multiselect(
            "Interests", INTEREST_OPTIONS, default=["Food", "History"],
            accept_new_options=True, max_selections=10,
            help="Pick from the list or type your own.",
        )
        notes = st.text_area(
            "Special requests", max_chars=500,
            placeholder="e.g. vegetarian food, travelling with kids, avoid long walks",
        )
        st.caption(f"Trips can be up to {MAX_TRIP_DAYS} days. * required")
        submitted = st.form_submit_button("✨ Plan my trip", type="primary", width="stretch")

    if not submitted:
        return None
    try:
        return TripRequest(
            destination=destination, origin=origin, start_date=start, end_date=end,
            travelers=int(travelers), budget=float(budget), currency=currency,
            travel_style=style, interests=interests, notes=notes,
        )
    except TripValidationError as e:
        st.error("Please fix the following:\n\n" + "\n".join(f"- {err}" for err in e.errors))
        return None


class ProgressReporter:
    """Turns orchestrator events into live lines inside an ``st.status`` box."""

    def __init__(self, status):
        self.status = status

    def __call__(self, event: Event) -> None:
        icon = EVENT_ICONS.get(event.type, "•")
        if event.type is EventType.STEP_STARTED:
            self.status.update(label=event.message[:120])
        self.status.write(f"{icon} {event.message}")
        if event.type is EventType.PLAN_READY and event.data:
            self.status.markdown("\n".join(f"{i}. **{w}**: {t}" for i, (w, t) in enumerate(event.data, 1)))


def trip_summary(request: TripRequest) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Destination", request.destination)
    c2.metric("Duration", f"{request.num_days} days")
    c3.metric("Travelers", request.travelers)
    c4.metric("Budget / day", f"{request.budget_per_day:,.0f} {request.currency}")


def results_view(result: TripPlanResult) -> None:
    """Show the final plan plus each agent's raw work in tabs."""
    trip_summary(result.request)
    for warning in result.warnings:
        st.warning(warning)

    grouped = result.outputs_by_worker()
    worker_tabs = [k for k in TAB_LABELS if k in grouped]
    tabs = st.tabs(["📋 Final plan", *(TAB_LABELS[k] for k in worker_tabs), "🧠 Agent log"])

    with tabs[0]:
        if result.approved:
            st.success("Approved by the Quality Reviewer.")
        st.markdown(result.final_plan)
        st.download_button(
            "⬇️ Download plan (.md)", to_markdown(result), file_name=safe_filename(result),
            mime="text/markdown", width="stretch",
        )

    for tab, key in zip(tabs[1:-1], worker_tabs):
        with tab:
            for step in grouped[key]:
                st.caption(f"Task: {step.task}")
                st.markdown(step.output)

    with tabs[-1]:
        agent_log(result)


def agent_log(result: TripPlanResult) -> None:
    st.markdown("#### Hand-offs")
    if result.used_fallback_plan:
        st.info("The default plan was used because the planner's reply was unusable.")
    for i, step in enumerate(result.steps, 1):
        status = "✅" if step.ok else f"❌ {step.error}"
        st.markdown(f"{i}. **{step.worker_name}** {status}  \n   _{step.task}_")

    st.markdown("#### Reviews")
    if not result.reviews:
        st.write("No review rounds ran.")
    for review in result.reviews:
        label = f"Round {review.round}: {'APPROVED ✅' if review.approved else 'changes requested ✏️'}"
        with st.expander(label, expanded=False):
            st.markdown(review.feedback)
