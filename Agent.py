import asyncio
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional
import httpx

load_dotenv()

from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams
from agents.extensions.memory import SQLAlchemySession
from sqlalchemy.ext.asyncio import create_async_engine
from langfuse import get_client, observe, propagate_attributes
from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor

langfuse = get_client()
OpenAIAgentsInstrumentor().instrument()

from agents import (
    Agent,
    Runner,
    AsyncOpenAI,
    OpenAIChatCompletionsModel,
    handoff,
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

external_client: AsyncOpenAI = AsyncOpenAI(
    api_key=GEMINI_API_KEY,
    base_url=BASE_URL,
)

model: OpenAIChatCompletionsModel = OpenAIChatCompletionsModel(
    model="gemini-3.1-flash-lite",
    openai_client=external_client
)

class Output(BaseModel):
    key_insights: list[str]
    cites: Optional[str]


# ── Short-term memory: one async engine reused for every SQLAlchemySession ─────
# SESSION_DB_URL points at Postgres in compose; falls back to a local SQLite file
# so `python Agent.py` still works outside Docker.
SESSION_DB_URL = os.getenv("SESSION_DB_URL", "sqlite+aiosqlite:///./sessions.db")
session_engine = create_async_engine(SESSION_DB_URL)

# Compaction rule: once a conversation exceeds MAX_TURNS user turns, the oldest
# SUMMARIZE_TURNS are collapsed into a single summary item to bound context/cost.
MAX_TURNS = 15
SUMMARIZE_TURNS = 10


async def _maybe_compact(session: "SQLAlchemySession") -> None:
    """If the conversation exceeds MAX_TURNS user turns, summarize the oldest
    SUMMARIZE_TURNS and replace them with one summary item, keeping the rest."""
    items = await session.get_items()

    # Index each item by which user turn it belongs to (a user message opens a turn).
    user_turn_count = sum(1 for it in items if it.get("role") == "user")
    if user_turn_count <= MAX_TURNS:
        return

    # Find the item index where the (SUMMARIZE_TURNS+1)-th user turn starts; everything
    # before it is the "old" slice we summarize, everything from it onward is kept.
    seen_users = 0
    split_at = len(items)
    for idx, it in enumerate(items):
        if it.get("role") == "user":
            seen_users += 1
            if seen_users == SUMMARIZE_TURNS + 1:
                split_at = idx
                break

    old_items = items[:split_at]
    kept_items = items[split_at:]
    if not old_items:
        return

    summarizer = Agent(
        name="Summarizer",
        instructions=(
            "You compress earlier conversation history. Produce a concise factual "
            "summary capturing the user's questions, key findings, and any "
            "decisions or context needed to answer future follow-ups. No preamble."
        ),
        model=model,
    )
    convo_text = "\n".join(
        f"{it.get('role', 'unknown')}: {it.get('content', '')}" for it in old_items
    )
    summary_result = await Runner.run(
        summarizer, f"Summarize this earlier conversation:\n\n{convo_text}"
    )
    summary_item = {
        "role": "user",
        "content": f"[Summary of earlier conversation]\n{summary_result.final_output}",
    }

    await session.clear_session()
    await session.add_items([summary_item] + kept_items)


from langfuse import get_client, observe, propagate_attributes

langfuse = get_client()

@observe(name="mcp_research")
async def run_research(
    topic: str,
    user_id: str | None = None,
    session_id: str | None = None,
) -> Output:

      # Bind the Chainlit-provided user/session ids onto this trace so every
      # message in one conversation thread groups under the same Langfuse session.
      with propagate_attributes(user_id=user_id, session_id=session_id):

        params = MCPServerStreamableHttpParams(
          url=os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8001/mcp"),
)

        async with MCPServerStreamableHttp(name="ResearchMCP",params=params) as mcp_client:

         researcher_prompt = langfuse.get_prompt("Researcher agent")
         display_prompt = langfuse.get_prompt("Display")

         display_agent = Agent(
            name="Display",
            instructions=display_prompt.compile(),
            model=model,
            output_type=Output,
         )

         agent = Agent(
            name="Researcher",
            instructions=researcher_prompt.compile(),
            model=model,
            mcp_servers=[mcp_client],
            handoffs=[display_agent],
         )

         # Per-conversation short-term memory keyed by the Chainlit session id.
         # Without a session id (e.g. local main()) we skip persistence.
         session = (
            SQLAlchemySession(session_id, engine=session_engine, create_tables=True)
            if session_id
            else None
         )
         if session is not None:
            await _maybe_compact(session)

         try:
            result = await Runner.run(agent, f"Research on: {topic}", session=session)
            final = result.final_output
            langfuse.update_current_span(output={"result": str(final)})
            return final

         except Exception as e:
            langfuse.update_current_span(
                output={"error": str(e)},
                metadata={"error_type": type(e).__name__}
            )
            raise


async def main():
    topic = "which countries are hosting AI research labs?"
    result = await run_research(topic)
    print(result)
    langfuse.flush()


if __name__ == "__main__":
    asyncio.run(main())
