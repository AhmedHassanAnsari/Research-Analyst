import os
from typing import Optional

import chainlit as cl
import httpx

API_URL = os.getenv("RESEARCH_API_URL", "http://127.0.0.1:8000/research")
DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID", "Ahmed")


@cl.oauth_callback
async def oauth_callback(
    provider_id: str,
    token: str,
    raw_user_data: dict,
    default_user: cl.User,
    id_token: Optional[str] = None,
) -> Optional[cl.User]:
    # The provider (Google/GitHub) has already verified the identity; we just
    # trust the resulting user. default_user.identifier is the provider's
    # email/username and is the stable key Chainlit upserts into "User".
    return default_user


def _current_user_id() -> str:
    user = cl.user_session.get("user")
    if user and getattr(user, "identifier", None):
        return user.identifier
    return DEFAULT_USER_ID


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("user_id", _current_user_id())
    await cl.Message(
        content="Welcome to the Research Analyst. Ask me to research any topic and I'll dig in."
    ).send()


@cl.on_chat_resume
async def on_chat_resume(thread):
    # Reopening a past thread: rebind the user so follow-up messages carry the
    # right ids. The agent session_id is derived from thread_id at send time,
    # and Chainlit sets thread_id to the resumed thread's id, so short-term
    # memory reconnects to this thread's existing history automatically.
    cl.user_session.set("user_id", _current_user_id())


@cl.on_message
async def on_message(message: cl.Message):
    payload = {
        "query": message.content,
        "user_id": cl.user_session.get("user_id") or _current_user_id(),
        # thread_id is stable per conversation (new chat -> fresh id, resumed
        # thread -> original id), so it doubles as the agent's session key.
        "session_id": cl.context.session.thread_id,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        resp = await client.post(API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

    insights = "\n".join(f"- {item}" for item in data.get("key_insights", []))
    cites = data.get("cites")

    if insights:
        content = f"### Key Insights\n{insights}"
        if cites:
            content += f"\n\n**Sources:** {cites}"
    elif data.get("message"):
        content = data["message"]
    else:
        content = "No insights returned."

    await cl.Message(content=content).send()
