# AskCipher
# Junior Developer Interview Case
(Shareable Candidate Version + Internal Evaluation Guide)

---

# SECTION A — CANDIDATE EXERCISE

(This section is intended to be shared with the candidate)

## Overview

At AskCipher, our platform is not a simple chatbot or standard CRUD application.

AskCipher is an AI-powered enterprise platform that includes:

- an AI agent built on LangGraph that reasons, selects tools, and takes actions
- a FastAPI gateway layer that handles authentication, validation, and proxying
- stateful tool execution where tools read from and write to a shared conversation state
- PostgreSQL for persistent storage
- integrations with enterprise systems such as ERP, CRM, HR, and other business applications

This exercise simulates the kind of development work a junior developer at AskCipher would do in their first weeks: understanding an existing agent architecture, building a new feature end-to-end, reviewing code for production readiness, and thinking about system design.

You are encouraged to use any AI coding tools you are comfortable with (Claude Code, Cursor, Copilot, ChatGPT, etc.). We use these tools daily at AskCipher — what matters is how effectively you use them, not whether you use them. If possible, please keep a brief log or screen recording of your work process. We may ask about your approach during the debrief.

## Architecture Context

The repo you'll be working in is a simplified version of our production architecture. In production, AskCipher has three main backend services:

```
Frontend → Server (:8000) → Hinge (:9000) → Pointer (:9001) → External APIs
                ↓                ↓
           PostgreSQL (shared database)
```

- **Server** — The public-facing API gateway. Handles JWT authentication, request validation, and proxies requests to internal services. The frontend can ONLY talk to Server.
- **Hinge** — The AI agent orchestration service. Runs a LangGraph ReAct agent that reasons about user requests, selects tools, executes them, and produces responses. Manages conversation state, memory, and tool execution.
- **Pointer** — The integration hub. Handles OAuth flows and API calls to external enterprise systems (Salesforce, NetSuite, Google Workspace, etc.).

### In This Exercise

This repo simplifies the architecture into a single process while maintaining the code-level separation:

```
src/
├── api/                  ← "Server" — FastAPI gateway
│   ├── main.py           # App entrypoint, lifespan, health check
│   ├── routes.py         # API endpoints (proxy to agent + DB)
│   ├── schemas.py        # Pydantic request/response models
│   └── database.py       # PostgreSQL connection pool + queries
│
├── react_agent/          ← "Hinge" — LangGraph agent
│   ├── graph.py          # ReAct agent (call_model ↔ tools cycle)
│   ├── state.py          # State with reducers + user context
│   ├── tools.py          # Tool registry (search_and_store example)
│   ├── prompts.py        # System prompt template
│   ├── context.py        # Runtime configuration
│   └── utils.py          # Helpers (model loading, message parsing)
```

### Key Concepts

**The ReAct Loop**
```
User message → call_model (LLM reasons) → tool calls? → execute tools → call_model again → ... → final response
```
The agent thinks, decides which tools to use, executes them, observes the results, and repeats until it has a final answer.

**State and Reducers**
The agent maintains state during a conversation. Some fields use *reducers* — functions that merge new values with existing ones instead of replacing them. For example, `search_results` uses an append-only reducer that accumulates search results throughout the session, deduplicating by query. Study `state.py` to understand this pattern.

**Tools and the Command Pattern**
Tools come in two flavors:
1. *Simple tools* — return a string directly (the LLM sees the result)
2. *Stateful tools* — return a `Command` object that updates the agent's state via reducers AND sends a message back to the LLM

Study `tools.py` to see both patterns. The `search_and_store` tool demonstrates the stateful `Command` pattern, including how it reads `user_id` and `org_id` from the injected state.

**API Gateway Pattern**
The API layer (`src/api/`) handles validation and user context, then delegates to the agent. It does NOT contain business logic — that lives in the agent and its tools. After the agent runs, the API layer persists results to PostgreSQL. Study `routes.py` to see this pattern.

## Setup

### Prerequisites
- Python 3.11+
- Docker and Docker Compose
- An Anthropic API key
- A Tavily API key (free tier: https://tavily.com)

### Getting Started

```bash
# Clone and enter the repo
git clone <repo-url>
cd jr-dev-case

# Copy environment file and add your API keys
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY and TAVILY_API_KEY

# Option A: Run with Docker (recommended)
docker-compose up --build
# API available at http://localhost:8000
# API docs at http://localhost:8000/docs

# Option B: Run locally
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows
pip install -e ".[dev]"
# Start Postgres separately, then:
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Verify Setup

```bash
# Health check
curl http://localhost:8000/health
# Expected: {"status": "ok"}

# Test chat (requires API keys)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "user_id": "test-user", "org_id": "test-org"}'
```

### Run Tests

```bash
# All unit tests
python -m pytest tests/unit_tests/ -v

# Specific test file
python -m pytest tests/unit_tests/test_state.py -v
```

## The Exercise

You will build a **message classification feature** end-to-end — from the LangGraph tool to the API endpoint to the database. This mirrors exactly the kind of feature work a junior developer does at AskCipher.

The classification tool should accept a text message, call an LLM to classify it with structured output, and return a classification with: `category`, `urgency`, `suggested_action`, and `confidence`.

We are not looking for the most complex solution. We are looking for clean code that follows the patterns already established in the codebase.

---

### Step 1: Build the Classification Tool (~45 min)

Create a `classify_message` tool in `src/react_agent/tools.py` that:

1. Accepts a `text` parameter (the message to classify)
2. Calls an LLM to classify the text into structured output with these fields:
   - `category` (string) — e.g., "question", "request", "complaint", "feedback", "general"
   - `urgency` (string) — e.g., "low", "medium", "high"
   - `suggested_action` (string) — what should be done about this message
   - `confidence` (float) — 0.0 to 1.0
3. Uses the `Command` pattern to store the classification in state (like `search_and_store` does)
4. Returns the classification result as a formatted message to the LLM
5. Reads `user_id` and `org_id` from the injected state
6. Has a clear, descriptive docstring (this is what the LLM reads to decide when to use your tool)
7. Is registered in the `TOOLS` list

**Hints:**
- Study `search_and_store` in `tools.py` for the full Command pattern
- For structured LLM output, you can use LangChain's `with_structured_output()` or parse a tool-use response
- The classification LLM call can use the same model the agent uses, or a smaller/faster one

### Step 2: Wire the State (~30 min)

Add state management for classifications in `src/react_agent/state.py`:

1. Write a reducer function (like `add_search_results`) for classifications
2. Add a `classifications` field to the `State` class using your reducer
3. Decide on your deduplication strategy — what makes a classification "the same"?

### Step 3: Build the API Layer (~60 min)

Create the API endpoints and database support:

**Database** — Add a `classifications` table to `init.sql`:
- Think about what columns you need (hint: look at `search_history` for the pattern)
- Add appropriate indexes

**Query functions** — Add to `src/api/database.py`:
- `store_classification()` — insert a classification record
- `fetch_classifications()` — retrieve classifications for a user, with optional filters

**Schemas** — Add to `src/api/schemas.py`:
- Request and response models for your classification endpoints

**Endpoints** — Add to `src/api/routes.py`:
- `POST /api/v1/classify` — accepts text + user context, runs classification (either directly or through the agent), stores result, returns it
- `GET /api/v1/classifications/{user_id}` — retrieves stored classifications with optional filtering

**Important:** Follow the patterns already in the code. Study how `/chat` and `/searches` are built.

### Step 4: Write Tests (~30 min)

Add tests that cover your new code:

1. **Reducer tests** — Add to `tests/unit_tests/test_state.py`:
   - Test that your reducer appends correctly
   - Test your deduplication logic
   - Test edge cases (empty lists, etc.)

2. **API tests** — Add to `tests/unit_tests/test_routes.py`:
   - Test your new endpoints (mock the agent/database like existing tests do)
   - Test validation (missing required fields should return 422)
   - Test the happy path

### Step 5: Code Review (~30 min)

Before building on top of the existing codebase, every developer should review the code they're extending.

Review `src/api/routes.py` carefully. Identify any issues you find related to:
- Security
- Error handling
- Production readiness

For each issue:
1. Describe what the problem is
2. Explain why it matters in production
3. Suggest a fix

Write your findings in a file called `CODE_REVIEW.md` in the project root.

### Step 6: Design Question (~15 min)

Answer the following in a file called `DESIGN.md` in the project root:

> The product team wants to add a feature where the agent learns from corrections. When a user says "that classification was wrong — it should be X", the agent remembers and improves future classifications for similar messages.
>
> How would you approach this? Consider:
> - Where does the correction get stored?
> - How does it influence future classifications?
> - What are the risks or failure modes?
> - How would you test this?

No code required. We are looking for clear thinking about data flow, storage, and edge cases.

## Deliverables

Please provide:

1. Your code changes (all modified and new files)
2. `CODE_REVIEW.md` with your review of the existing code
3. `DESIGN.md` with your design answer
4. Instructions for running your solution
5. A brief note on how you used AI tools during the exercise (which tools, for which parts, what worked / what didn't)

## What We Care About

We are not looking for the most complex solution.

We are looking for someone who:
- reads and understands existing code before writing new code
- follows established patterns rather than inventing new ones
- writes clean, tested, production-aware code
- thinks about security, error handling, and edge cases
- uses AI tools effectively and critically — not blindly
- can communicate design decisions clearly

## Time Expectation

This exercise is designed to take approximately **3–4 hours**. If you find yourself spending significantly longer, focus on the parts you've completed and note any areas you would improve given more time.

---
---

# SECTION B — INTERNAL INTERVIEWER GUIDE

(Do NOT share with candidates)

## Objectives

This case evaluates whether the candidate can work effectively in an AI agent codebase — a very different environment from a standard web application. The candidate should demonstrate they can:

1. Read and comprehend an unfamiliar but well-structured codebase quickly
2. Follow established patterns to build a new feature end-to-end
3. Work with LangGraph tools, state management, and the Command pattern
4. Write correct API endpoints with proper validation and error handling
5. Identify real production bugs through careful code review
6. Use AI coding tools effectively and critically
7. Think about system design at a junior level

## What We Are Evaluating

### 1 — Pattern Recognition and Code Comprehension

The entire exercise is designed around "follow the pattern." The codebase has one complete working example (search_and_store → state reducer → API endpoints → tests). The candidate must study it and replicate it for classifications.

**Strong candidates:**
- Read all the existing code before writing anything
- Ask clarifying questions about patterns they don't understand
- Follow the naming conventions, file organization, and code style
- Understand why `InputState` vs `State` exists (input interface vs internal state)

**Weak candidates:**
- Start writing code immediately without reading existing patterns
- Create new file structures instead of following the existing one
- Mix business logic into the API layer (it belongs in the agent/tools)
- Don't understand what reducers do or why they exist

### 2 — LLM Integration and Structured Output

The classification tool requires calling an LLM and getting structured output. This tests whether they understand the LLM-as-a-function pattern.

**Strong candidates:**
- Define a clear output schema (Pydantic model or dict structure)
- Use `with_structured_output()` or equivalent for reliable parsing
- Handle cases where the LLM returns unexpected output
- Write a good tool docstring (this IS the LLM's understanding of when to use the tool)
- Choose appropriate model parameters (temperature, max_tokens)

**Weak candidates:**
- Try to parse free-text LLM output with regex
- Don't validate the LLM's response
- Write vague or misleading tool docstrings
- Don't consider what happens when the LLM call fails

### 3 — State Management

The reducer is a core pattern. Can they write one correctly?

**Strong candidates:**
- Write a reducer that follows the same signature pattern as `add_search_results`
- Choose a sensible deduplication strategy (by input text? by timestamp? by combination?)
- Write thorough tests for the reducer (append, dedup, empty cases)
- Understand that reducers are *merge* functions, not *set* functions

**Weak candidates:**
- Replace instead of merge (overwrite state instead of appending)
- Don't dedup at all (unbounded state growth)
- Skip testing the reducer
- Don't understand the `Annotated[list[...], reducer_fn]` pattern

### 4 — API Design and Database

Can they build a proper endpoint pair following the proxy pattern?

**Strong candidates:**
- Follow the exact pattern from `/chat` and `/searches`
- Design a sensible database schema (proper types, indexes, JSONB where appropriate)
- Pass `user_id` and `org_id` through the full chain (API → agent → tool → DB)
- Write Pydantic schemas with proper validation (Field, min_length, etc.)
- Handle errors correctly in the API layer

**Weak candidates:**
- Put business logic in the API layer
- Forget to persist results to the database
- Don't pass user context through the chain
- Skip validation on request schemas
- Return raw database rows without Pydantic serialization

### 5 — Code Review (Critical — Tests Judgment)

There are **2 intentional bugs** planted in `src/api/routes.py`. This step tests whether the candidate actually reads existing code critically before extending it.

#### Bug 1: `except Exception` swallowing `HTTPException`

**Location:** `routes.py`, `get_searches` function (lines 107-113)

```python
try:
    if not user_id.strip():
        raise HTTPException(status_code=400, detail="user_id cannot be blank")
    rows = await fetch_search_results(user_id, org_id, limit)
except Exception as e:
    logger.error("Failed to fetch searches: %s", e)
    raise HTTPException(status_code=500, detail="Database query failed")
```

**Problem:** The `raise HTTPException(400)` inside the `try` block gets caught by the broad `except Exception`, which re-raises it as a 500. A blank user_id should return 400 but returns 500 instead.

**Expected fix:** Add `except HTTPException: raise` before `except Exception as e:`, or restructure so validation happens outside the try block.

**Severity:** High — wrong status codes in production make debugging difficult and break client error handling.

#### Bug 2: API Key Logged in Debug Statement

**Location:** `routes.py`, `chat` function (lines 49-54)

```python
logger.debug(
    "Processing chat for user=%s org=%s model_config=%s",
    request.user_id,
    request.org_id,
    os.environ.get("ANTHROPIC_API_KEY", "not-set"),
)
```

**Problem:** Logs the raw `ANTHROPIC_API_KEY` to whatever log aggregation system is in use (CloudWatch, Datadog, etc.). In production with DEBUG logging enabled, this leaks credentials.

**Expected fix:** Remove the API key from the log entirely, or at minimum mask it (e.g., `key[:8] + "..."`).

**Severity:** Critical — credential leak to log storage systems.

**Evaluation:**
- Finding both bugs: Strong signal — reads code carefully, security-aware
- Finding one bug: Acceptable — shows some review discipline
- Finding neither: Red flag — either didn't review, or reviewed superficially
- Bonus: Candidate also flags other improvements (e.g., the broad `except Exception` in `chat` has the same potential issue if someone adds validation later)

### 6 — AI Tool Usage

We explicitly told the candidate to use AI tools and log their process. This is not a trick — we genuinely want to assess how they work with AI.

**Strong signals:**
- Uses AI for boilerplate and repetitive code, writes business logic themselves
- Reviews and understands AI-generated code before accepting it
- Iterates on AI output rather than accepting first response
- Knows when NOT to use AI (architecture decisions, security review)
- Can explain code the AI generated ("Why did you do it this way?")

**Weak signals:**
- Blindly accepts all AI output without review
- Can't explain code in their own solution
- Uses AI for the code review step and misses bugs (AI tools commonly miss the `except Exception` swallowing pattern)
- Doesn't validate that AI-generated code follows the existing patterns

**During debrief, ask:**
- "Walk me through how you approached Step 1. What did you write yourself vs what did AI generate?"
- "In the code review, did you use AI tools? What did they find vs what they missed?"
- "Show me a case where you modified or rejected what the AI suggested."

### 7 — Design Thinking (Step 6)

The correction/learning question tests whether they can think about feedback loops, data integrity, and system design.

**Strong answers mention:**
- Storing corrections alongside the original classification (linkage)
- Using corrections as few-shot examples in future classification prompts
- Risk of adversarial corrections (user intentionally mis-correcting)
- Risk of concept drift (corrections from one context applied to another)
- Testing with known correction → re-classification pairs
- Scope: per-user corrections vs org-wide vs global

**Weak answers:**
- "Fine-tune the model" (shows no understanding of prompt engineering patterns)
- No consideration of edge cases or failure modes
- No testing strategy
- Overly complex architecture for what is a simple feature

### 8 — Testing Quality

**Strong candidates:**
- Follow the existing test patterns (TestClient, mocked deps)
- Test both happy paths and error cases
- Test the reducer independently (pure function tests)
- Mock external dependencies (LLM calls, database)
- Tests are readable and well-organized

**Weak candidates:**
- Skip tests entirely
- Only test happy paths
- Don't mock — try to call real services
- Tests are brittle or coupled to implementation details

## Follow-Up Questions for Debrief

Ask these during the debrief conversation (30 min):

**Architecture Understanding:**
- "Why do we separate the API layer from the agent? What would break if we put the classification logic directly in the route handler?"
- "What happens to the state between requests? Where does it go?"
- "If two users send messages at the same time, how does the state stay separate?"

**Production Thinking:**
- "How would you deploy this classification feature without downtime?"
- "What happens if the classification LLM call takes 30 seconds? How would you handle that?"
- "How would you monitor whether the classification feature is working correctly in production?"

**Growth Indicators:**
- "What would you do differently if you had more time?"
- "What was the hardest part of this exercise?"
- "What patterns in this codebase were new to you? How did you learn them?"

## Scoring Guide

| Area | Weight | Excellent | Acceptable | Insufficient |
|------|--------|-----------|------------|-------------|
| Pattern following | 25% | Follows all patterns, clean integration | Mostly follows, minor deviations | Creates new patterns, ignores existing code |
| LLM tool implementation | 20% | Structured output, error handling, good docstring | Works but fragile or missing edge cases | Broken or doesn't use structured output |
| State + Reducers | 10% | Correct reducer, dedup, tested | Works but missing dedup or tests | Wrong pattern (replace instead of merge) |
| API + DB | 15% | Full CRUD, schemas, user context flows through | Endpoints work but missing validation or context | Broken or missing endpoints |
| Code Review | 15% | Finds both bugs, explains clearly | Finds one bug | Finds neither |
| Tests | 10% | Reducer + API tests, edge cases | Some tests, happy path only | No tests |
| Design Question | 5% | Clear thinking, edge cases, testing | Reasonable but shallow | No answer or "fine-tune the model" |
