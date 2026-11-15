"""Streamlit entry point.

Run from the project root:  streamlit run ui/app.py
"""

import logging
import sys
from pathlib import Path

# `streamlit run ui/app.py` only puts ui/ on the import path; add the project
# root so `import travel_planner` works.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from travel_planner import ConfigError, LLMError, PlanningError, create_orchestrator, load_settings  # noqa: E402
from ui.components import ProgressReporter, results_view, trip_form  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ui")


def sidebar() -> None:
    with st.sidebar:
        st.header("How it works")
        st.markdown(
            "1. **Orchestrator** splits your trip into tasks\n"
            "2. **Destination Researcher** finds places, food and tips\n"
            "3. **Logistics Planner** covers transport and where to stay\n"
            "4. **Budget Analyst** estimates costs\n"
            "5. **Itinerary Writer** builds the day-by-day plan\n"
            "6. **Quality Reviewer** checks it and requests fixes"
        )
        st.caption("Built with pure Python, no agent frameworks.")
        if st.session_state.get("result") and st.button("🔄 Start a new plan", width="stretch"):
            st.session_state.pop("result", None)
            st.rerun()


def run_planner(request) -> None:
    """Run the agents with live progress; store the result or show a friendly error."""
    with st.status("Agents are planning your trip…", expanded=True) as status:
        try:
            orchestrator = create_orchestrator(on_event=ProgressReporter(status))
            st.session_state["result"] = orchestrator.run(request)
            status.update(label="Your travel plan is ready!", state="complete", expanded=False)
        except ConfigError as e:
            status.update(label="Configuration problem", state="error")
            st.error(f"⚙️ {e}")
        except LLMError as e:
            status.update(label="AI service problem", state="error")
            st.error(f"🤖 {e}")
        except PlanningError as e:
            status.update(label="Planning failed", state="error")
            st.error(f"🗺️ {e}")
        except Exception:  # last-resort safety net so the app never shows a raw crash
            logger.exception("Unexpected error while planning")
            status.update(label="Unexpected error", state="error")
            st.error("Something unexpected went wrong. Please try again; details are in the terminal log.")


def main() -> None:
    st.set_page_config(page_title="Travel Planner Agent", page_icon="✈️", layout="wide")
    st.title("✈️ Travel Planner Agent")
    st.caption("A team of AI agents plans your trip: research, logistics, budget, itinerary and review.")
    sidebar()

    # Fail early and clearly if the API key is missing.
    try:
        load_settings()
    except ConfigError as e:
        st.error(f"⚙️ {e}")
        st.stop()

    request = trip_form()
    if request is not None:
        st.session_state.pop("result", None)
        run_planner(request)

    if result := st.session_state.get("result"):
        st.divider()
        results_view(result)


main()
