# ✈️ Travel Planner Agent

A **multi-agent AI travel planner** built with **pure Python**, with no agent frameworks (no CrewAI, LangChain, LangGraph, AutoGen, etc.).

You describe the trip you want (destination, dates, budget, interests), and a team of specialised AI agents works together to put together a complete travel plan.

> 🚧 **Status: In development.** This README will be updated as features are completed.

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
| **Coordinator Agent** | Understands the user's request, delegates tasks to other agents, and combines the final plan |
| **Destination Agent** | Suggests places to visit, attractions, and local tips |
| **Itinerary Agent** | Builds a day-by-day schedule for the trip |
| **Budget Agent** | Estimates costs (stay, food, transport, activities) and keeps the plan within budget |

*(Agents may be added or changed as the project develops.)*

### How it works (planned flow)

```
User request
     │
     ▼
Coordinator Agent ──► Destination Agent
     │            ──► Itinerary Agent
     │            ──► Budget Agent
     ▼
Final travel plan
```

---

## 🛠️ Tech Stack

- **Python 3.10+** (developed on Python 3.13)
- **[Groq](https://pypi.org/project/groq/)**: Python SDK for the Groq LLM API
- **[python-dotenv](https://pypi.org/project/python-dotenv/)**: loads the API key from a `.env` file
- **Model:** `openai/gpt-oss-120b` (via Groq)

---

## 📁 Project Structure

```
TravelPlannerAgent/
├── agent.py           # Agent logic (agents, tools, orchestration)
├── config.py          # Loads API key, creates Groq client, sets model name
├── requirements.txt   # Python dependencies
├── .env.example       # Template for environment variables
├── .env               # Your real API key (NOT committed to Git)
├── .gitignore
├── LICENSE
└── README.md
```

*(Structure will be updated as new files are added.)*

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

```bash
python agent.py
```

*(Usage instructions will be added once the agent is complete.)*

---

## 💡 Usage

*Coming soon: example prompts and sample output.*

---

## 🗺️ Roadmap

- [x] Project setup (Groq client, environment config)
- [ ] Basic agent loop (LLM call + message history)
- [ ] Tool calling with pure Python functions
- [ ] Specialist agents (Destination, Itinerary, Budget)
- [ ] Coordinator agent for multi-agent orchestration
- [ ] Command-line interface for user input
- [ ] Final travel plan output

---

## 🧯 Troubleshooting

| Problem | Solution |
|---|---|
| `GROQ_API_KEY not found` | Make sure `.env` exists in the project folder and contains your key |
| `model not found` error | The model name may have changed. Check [console.groq.com/docs/models](https://console.groq.com/docs/models) and update `MODEL` in `config.py` |
| `ModuleNotFoundError` | Activate the virtual environment, then run `pip install -r requirements.txt` |

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.
