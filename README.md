# Research Analyst

An AI research assistant that answers open-ended questions by searching the web, reasoning over the results, and returning structured, cited insights — with a persistent chat history you can reopen at any time.

It is built as four small, independently deployable services wired together over HTTP, and is instrumented end-to-end with [Langfuse](https://langfuse.com) for tracing, prompt management, and evaluation.

## Features

- **Multi-agent research pipeline** — an Orchestrator hands off to a Researcher (web search via MCP) which hands off to a Display agent that returns structured JSON (`key_insights`, `cites`).
- **Web search grounding** — a Model Context Protocol (MCP) server exposes a Tavily-backed `search_web` tool.
- **Conversational memory** — per-conversation short-term memory in Postgres, with automatic summarization/compaction once a conversation grows long.
- **Persistent thread history** — a sidebar of past conversations you can reopen; reopening a thread reconnects to that thread's memory, and a new chat starts fresh.
- **OAuth login** — sign in with Google or GitHub (native Chainlit OAuth, no separate auth service).
- **Full observability** — every conversation is traced in Langfuse, grouped by user and session.
- **Evaluation harness** — a Langfuse dataset + LLM-as-a-judge experiment to score the pipeline.

## Architecture

Four separate processes, each with its own Dockerfile, connected over HTTP:

```
Chainlit UI (chainlit_app.py, :9000)      ← user entry point, OAuth login, chat history
  → HTTP POST /research → FastAPI (api.py, :8000)
    → run_research()  (Agent.py)
      → Orchestrator agent → Researcher agent → Display agent   (OpenAI Agents SDK handoffs)
                                  ↓ MCP (streamable HTTP)
                                MCP server (mcp_server.py, :8001) → Tavily web search
```

| Component | File | Port | Role |
|-----------|------|------|------|
| UI | `chainlit_app.py` | 9000 | Chainlit chat interface, OAuth, thread persistence |
| Agent API | `api.py` → `Agent.py` | 8000 | FastAPI wrapper around the agent pipeline |
| MCP server | `mcp_server.py` | 8001 | `search_web` tool backed by Tavily |
| Postgres | (compose) | 5432 | Short-term memory **and** Chainlit thread history |

**Model:** Google Gemini (`gemini-3.1-flash-lite`) accessed through the OpenAI-compatible endpoint via the OpenAI Agents SDK.

**Agent instructions live in Langfuse**, not in code — they are fetched at runtime with `langfuse.get_prompt(...)`. Tuning agent behavior means editing the prompt in Langfuse.

### Memory model

The same Postgres database backs two independent subsystems that connect with **different DSN schemes** so they never collide:

- **Short-term / conversational memory** (agent side) — `SQLAlchemySession` keyed by `session_id`, using `SESSION_DB_URL` with the `postgresql+asyncpg://` scheme. Once a conversation exceeds 15 user turns, the oldest 10 are summarized into a single item to bound context and cost.
- **Long-term / thread persistence** (UI side) — Chainlit's data layer, activated by `DATABASE_URL` with the raw `postgresql://` scheme.

The two are unified by using the Chainlit **`thread_id` as the agent `session_id`**: a new chat gets a fresh id (fresh memory), and reopening a thread reuses the original id (reconnects to that thread's history).

## Tech stack

Python 3.12 · [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) · [Model Context Protocol](https://modelcontextprotocol.io) · [FastAPI](https://fastapi.tiangolo.com) · [Chainlit](https://chainlit.io) · [Langfuse](https://langfuse.com) · [Tavily](https://tavily.com) · Postgres · Docker · [uv](https://github.com/astral-sh/uv)

## Getting started

### Prerequisites

- [uv](https://github.com/astral-sh/uv) and Python 3.12 (for local dev)
- Docker + Docker Compose (for the full stack)
- API keys: Google Gemini, Tavily, Langfuse (public + secret)
- OAuth apps for Google and/or GitHub (for login)

### Configuration

Create a `.env` file in the project root (it is gitignored):

```dotenv
# Model
GEMINI_API_KEY1=your-gemini-key

# Web search
TAVILY_API_KEY=your-tavily-key

# Observability + prompts (agent fetches its prompts from Langfuse at startup)
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com

# Postgres
POSTGRES_USER=research
POSTGRES_PASSWORD=research
POSTGRES_DB=research

# Short-term memory DSN (note the +asyncpg scheme)
SESSION_DB_URL=postgresql+asyncpg://research:research@localhost:5432/research
# Chainlit thread persistence DSN (note the RAW scheme — +asyncpg is rejected here)
DATABASE_URL=postgresql://research:research@localhost:5432/research

# Chainlit auth
CHAINLIT_AUTH_SECRET=generate-with-openssl-rand-base64-32
CHAINLIT_URL=http://localhost:9000

# OAuth providers
OAUTH_GOOGLE_CLIENT_ID=...
OAUTH_GOOGLE_CLIENT_SECRET=...
OAUTH_GITHUB_CLIENT_ID=...
OAUTH_GITHUB_CLIENT_SECRET=...
```

Generate the auth secret with: `openssl rand -base64 32`

### Run the full stack (Docker)

```bash
docker compose up
```

The UI is the entry point at **http://localhost:9000**. Images are pulled from GHCR. On the first run against a fresh Postgres volume, the Chainlit schema in `db/init/01_chainlit_schema.sql` is applied automatically; against an existing volume, apply it manually:

```bash
docker exec -i research-postgres psql -U research -d research -v ON_ERROR_STOP=1 < db/init/01_chainlit_schema.sql
```

### Run components individually (local dev)

Each process runs in its own shell and needs the `.venv` and `.env`:

```bash
uv sync                                                        # install dependencies
uv run uvicorn mcp_server:app --host 0.0.0.0 --port 8001       # MCP research server
uv run uvicorn api:app --port 8000                             # FastAPI agent API
uv run chainlit run chainlit_app.py --port 9000                # Chainlit UI
```

## Evaluation

A Langfuse dataset and an LLM-as-a-judge experiment score the pipeline end-to-end:

```bash
uv run python evaluation.py --seed   # create/upsert the eval dataset
uv run python evaluation.py --run    # run the experiment, print scores
```

Scorers: an in-code LLM judge (1–5 against a rubric) and a `has_citations` check. Results are recorded in Langfuse.

## Deployment

`.github/workflows/ci.yml` builds and pushes three images to GHCR — `research-analyst-agent`, `research-analyst-server`, and the UI image — each gated on a path filter so only the changed component rebuilds. Configuration is fully environment-driven, so production deployment (e.g. Kubernetes) is a matter of supplying secrets and the public callback URLs per environment.

## Project layout

```
Agent.py            # core research pipeline (agents, handoffs, short-term memory + compaction)
api.py              # FastAPI wrapper — POST /research
mcp_server.py       # MCP server exposing search_web (Tavily)
chainlit_app.py     # Chainlit UI: OAuth, chat, thread persistence
evaluation.py       # Langfuse dataset + LLM-as-a-judge experiment
db/init/            # Chainlit data-layer schema
docker-compose.yml  # full local stack
Dockerfile.agent    # }
Dockerfile.server   # } one image per service
Dockerfile.ui       # }
```
