import os
import uuid

import chainlit as cl
import httpx

API_URL = os.getenv("RESEARCH_API_URL", "http://127.0.0.1:8000/research")
DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID", "Ahmed")


@cl.on_chat_start
async def on_chat_start():
    # One session id per conversation thread; every message in this thread
    # reuses it so all Langfuse traces group under a single session.
    cl.user_session.set("user_id", DEFAULT_USER_ID)
    cl.user_session.set("session_id", str(uuid.uuid4()))
    await cl.Message(
        content="Welcome to the Research Analyst. Ask me to research any topic and I'll dig in."
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    payload = {
        "query": message.content,
        "user_id": cl.user_session.get("user_id"),
        "session_id": cl.user_session.get("session_id"),
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        resp = await client.post(API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

    insights = "\n".join(f"- {item}" for item in data.get("key_insights", []))
    cites = data.get("cites")

    content = f"### Key Insights\n{insights}" if insights else "No insights returned."
    if cites:
        content += f"\n\n**Sources:** {cites}"

    await cl.Message(content=content).send()
