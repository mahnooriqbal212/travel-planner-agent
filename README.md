# ✈️ Travel Planner Agent

A **multi-agent AI travel planner** built with **pure Python**, with no agent frameworks (no CrewAI, LangChain, LangGraph, AutoGen, etc.).

You describe the trip you want (destination, dates, budget, interests), and a team of specialised AI agents works together to put together a complete travel plan.

> 🚧 **Status: Working version.** This README will be updated as the project evolves.

---

## 📌 About the Project

Most AI agent projects rely on frameworks that hide how agents actually work. This project builds everything from scratch using **plain Python functions** and direct calls to a Large Language Model (LLM), to show the core ideas behind AI agents:

- **Agents as functions:** each agent is a Python function with its own system prompt and responsibility.
- **Tool calling:** agents can call Python functions (tools) to get information or do calculations.
- **Multi-agent orchestration:** a coordinator agent splits the user's request into tasks, sends each task to the right specialist agent, and combines their results.
- **No hidden magic:** the agent loop, message history, and tool handling are all written by hand.

The LLM is accessed through the **[Groq API](https://console.groq.com/)** for fast inference.

---

## 🤖 Planned Agents

| Agent | Responsibility |
|---|---|
| **Orchestrator (Planner)** | Reads the trip request and splits it into steps (JSON), choosing which worker does what |
| **Destination Researcher** | Attractions matching your interests, local food, weather, etiquette, safety & visa notes |
| **Logistics Planner** | Getting there, getting around, and the best areas/accommodation for your budget |
| **Budget Analyst** | Cost breakdown table (stay, food, transport, activities, 10% buffer) and whether it fits your budget |
| **Itinerary Writer** | Combines everything into the final day-by-day plan; also fixes issues the reviewer finds |
| **Quality Reviewer** | Critic: checks the plan against the request; replies `APPROVED` or lists fixes |

### How it works

```
Trip form (Streamlit / CLI)
        │  TripRequest — validated in Python, days & budget/day computed in Python
        ▼
 Orchestrator ──► plan: [{"worker": ..., "task": ...}, ...]
        │
        ├─► Destination Researcher ─┐
        ├─► Logistics Planner ──────┤  each worker sees the shared context
        ├─► Budget Analyst ─────────┤  (trip request + all earlier outputs)
        └─► Itinerary Writer ◄──────┘
                    │ draft
                    ▼
            Quality Reviewer ── APPROVED ──► Final plan
                    │ fixes
                    └──► Itinerary Writer (max 2 revision rounds)
```

---

## 🛠️ Tech Stack

- **Python 3.10+** (developed on Python 3.13)
- **[Groq](https://pypi.org/project/groq/)**: Python SDK for the Groq LLM API
- **[python-dotenv](https://pypi.org/project/python-dotenv/)**: loads the API key from a `.env` file
- **[Streamlit](https://streamlit.io/)**: web UI
- **[pytest](https://pytest.org/)**: tests
- **Model:** `openai/gpt-oss-120b` (via Groq)

---

## 📁 Project Structure

```
TravelPlannerAgent/
├── travel_planner/        # Core logic (no UI code)
│   ├── settings.py        # Loads .env settings safely (raises ConfigError, never exits)
│   ├── exceptions.py      # Custom error classes
│   ├── llm.py             # Groq wrapper: translates API errors into friendly messages
│   ├── models.py          # TripRequest (validation + budget maths) and result classes
│   ├── prompts.py         # Every agent's system prompt + the planner prompt
│   ├── agents.py          # Agent class and build_team()
│   ├── planner.py         # Orchestrator planning step with JSON fallbacks
│   ├── orchestrator.py    # Runs plan → workers → review loop, emits progress events
│   └── export.py          # Markdown export for download/saving
├── ui/                    # Streamlit UI only
│   ├── app.py             # Entry point: streamlit run ui/app.py
│   └── components.py      # Form, live progress, result tabs
├── tests/                 # pytest suite (uses a fake LLM; no API key or internet needed)
├── main.py                # Command-line version
├── agent_tech.py          # Class example this project is based on
├── config.py              # Used by agent_tech.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## ⚙️ Installation & Setup

### 1. Prerequisites

- [Python 3.10 or newer](https://www.python.org/downloads/)
- [Git](https://git-scm.com/downloads)
- A free **Groq API key**: sign up at [console.groq.com](https://console.groq.com/keys)

### 2. Clone the repository

```bash
git clone https://github.com/mahnooriqbal212/traveller-planner-agent.git
cd traveller-planner-agent
```

### 3. Create and activate a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

> On Windows, if you get an error about running scripts being disabled, run this once:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Add your API key

Copy the example environment file:

**Windows (PowerShell):**
```powershell
copy .env.example .env
```

**macOS / Linux:**
```bash
cp .env.example .env
```

Then open `.env` and paste your Groq API key:

```
GROQ_API_KEY=your_groq_api_key_here
```

> ⚠️ **Never commit your `.env` file.** It is already listed in `.gitignore`.

### 6. Run the project

**Web UI (Streamlit):**
```bash
streamlit run ui/app.py
```
It opens at http://localhost:8501.

**Command line:**
```bash
python main.py
```
Plans made from the CLI are also saved to the `output/` folder.

### 7. Run the tests

```bash
pytest
```
The tests use a fake LLM, so they are free, fast and need no internet connection.

### Optional settings (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Model to use |
| `MAX_REVISIONS` | `2` | Reviewer → writer fix rounds (0 disables the review) |
| `MAX_STEPS` | `8` | Maximum steps the planner may create |
| `MAX_RETRIES` | `2` | Automatic retries for rate limits / network errors |

---

## 💡 Usage

1. Enter your destination, dates, number of travelers, budget, travel style and interests.
2. Click **✨ Plan my trip** and watch each agent hand off to the next in the progress box.
3. Read the final plan, look at each agent's raw work in the tabs, and see every hand-off and review in **🧠 Agent log**.
4. Download the plan as a Markdown file.

A full run usually takes 1–2 minutes (5–7 LLM calls).

---

## 🗺️ Roadmap

- [x] Project setup (Groq client, environment config)
- [x] Agent class with role-based system prompts
- [x] Orchestrator that plans steps as JSON
- [x] Specialist workers (Researcher, Logistics, Budget, Writer)
- [x] Reviewer critic loop with revisions
- [x] Error handling (API errors, bad JSON, failed workers)
- [x] Streamlit UI and command-line interface
- [x] Automated tests
- [ ] Tool calling with pure Python functions (e.g. live weather / currency rates)

---

## 🧯 Troubleshooting

| Problem | Solution |
|---|---|
| `GROQ_API_KEY not found` | Make sure `.env` exists in the project folder and contains your key |
| `model not found` error | The model name may have changed. Check [console.groq.com/docs/models](https://console.groq.com/docs/models) and update `MODEL` in `config.py` |
| `ModuleNotFoundError` | Activate the virtual environment, then run `pip install -r requirements.txt` |
| `Groq rate limit reached` | The free tier limits requests per minute. Wait a minute and try again |
| `ModuleNotFoundError: travel_planner` | Run commands from the project root folder |

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.
