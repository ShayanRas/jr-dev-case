# AskCipher — Junior Developer Exercise

## Quick Start

```bash
# 1. Clone and set up
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY and TAVILY_API_KEY

# 2. Run with Docker
docker-compose up --build

# 3. Verify
curl http://localhost:8000/health          # → {"status": "ok"}
curl http://localhost:8000/docs            # → Swagger UI

# 4. Run tests
python -m pytest tests/unit_tests/ -v
```

**Alternative (no Docker):** `pip install -e ".[dev]"` then `uvicorn api.main:app --reload`
(You'll need a local Postgres instance with the schema from `init.sql`)

---

## Architecture

This repo is a simplified version of AskCipher's production backend. In production, three services handle different responsibilities:

```
Frontend → Server (:8000) → Hinge (:9000) → Pointer (:9001) → External APIs
                ↓                ↓
           PostgreSQL (shared database)
```

| Service | Role | In This Repo |
|---------|------|-------------|
| **Server** | API gateway — auth, validation, proxying | `src/api/` |
| **Hinge** | AI agent — LangGraph ReAct loop, tools, state | `src/react_agent/` |
| **Pointer** | Integration hub — external API calls | Tool functions call APIs directly |

This exercise runs everything in one process but maintains the **code-level separation** between layers.

---

## How It Works

### The ReAct Agent

The agent follows a reasoning loop:

```
User message → call_model (LLM thinks) → tool calls? → execute tools → call_model → ... → response
```

The graph is defined in `graph.py`:
```
__start__ → call_model → [has tool calls?] → tools → call_model → ... → __end__
```

### State and Reducers

The agent carries state throughout a conversation. Key concept: **reducers**.

```python
# In state.py — a reducer MERGES new values instead of replacing
def add_search_results(existing, new):
    existing_queries = {r["query"] for r in existing}
    return existing + [r for r in new if r["query"] not in existing_queries]

# The field uses the reducer via annotation
search_results: Annotated[list[dict], add_search_results] = field(default_factory=list)
```

User context (`user_id`, `org_id`) flows from the API layer into `InputState`, and the agent's tools can read it via `InjectedState`.

### Tools: Two Patterns

**Simple** — returns a string:
```python
async def search(query: str) -> str:
    return results
```

**Stateful** — returns a `Command` that updates state via reducers:
```python
@tool
async def search_and_store(
    query: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    *,
    state: Annotated[dict, InjectedState],
) -> Command:
    results = await do_search(query)
    return Command(update={
        "search_results": [{"query": query, "results": results, ...}],
        "messages": [ToolMessage(content=formatted, tool_call_id=tool_call_id)],
    })
```

Study `tools.py` for the complete example.

### API Gateway Pattern

The API layer (`src/api/`) validates requests, passes user context into the agent, and persists results to Postgres. It does **not** contain business logic — that lives in the agent and its tools.

```
POST /api/v1/chat → validate → invoke agent graph → persist results → respond
GET  /api/v1/searches/{user_id} → query database → respond
```

---

## Project Structure

```
src/
├── api/                          # "Server" — API gateway layer
│   ├── main.py                   # FastAPI app, lifespan (DB pool), CORS
│   ├── routes.py                 # Endpoints: /chat, /searches
│   ├── schemas.py                # Pydantic request/response models
│   └── database.py               # asyncpg pool + query functions
│
├── react_agent/                  # "Hinge" — AI agent layer
│   ├── graph.py                  # LangGraph StateGraph (ReAct loop)
│   ├── state.py                  # InputState + State with reducers
│   ├── tools.py                  # Tool registry (search_and_store)
│   ├── prompts.py                # System prompt template
│   ├── context.py                # Runtime config (model, prompt)
│   └── utils.py                  # Model loader, message text helper

tests/
├── unit_tests/
│   ├── test_state.py             # Reducer tests
│   ├── test_routes.py            # API endpoint tests (mocked deps)
│   └── test_configuration.py     # Context config tests

docker-compose.yml                # App + Postgres
Dockerfile                        # Python 3.11 container
init.sql                          # Database schema
```

---

## Key Files to Study

| File | What to learn |
|------|--------------|
| `src/react_agent/state.py` | How state flows, what reducers do, where user context lives |
| `src/react_agent/tools.py` | Both tool patterns (simple vs Command), InjectedState, docstrings |
| `src/react_agent/graph.py` | The ReAct loop, how call_model and tools connect |
| `src/api/routes.py` | The gateway pattern, how API invokes agent and persists results |
| `src/api/schemas.py` | Pydantic models for request validation and response formatting |
| `tests/unit_tests/test_state.py` | How to test reducers (pure functions, no infra needed) |
| `tests/unit_tests/test_routes.py` | How to test endpoints with mocked agent and database |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/chat` | Send message to agent, get response |
| `GET` | `/api/v1/searches/{user_id}` | Retrieve stored search results |

See full schemas at `http://localhost:8000/docs` when running.

---

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Claude API key |
| `TAVILY_API_KEY` | Yes | — | Tavily search API key |
| `DATABASE_URL` | No | `postgresql://postgres:postgres@postgres:5432/case_db` | Postgres DSN |
| `MODEL` | No | `anthropic/claude-sonnet-4-5-20250929` | LLM model to use |

---

## Exercise Instructions

See **INTERVIEW_CASE.md** for the full exercise.
