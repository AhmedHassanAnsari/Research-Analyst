import os

import chainlit as cl
import httpx

API_URL = os.getenv("RESEARCH_API_URL", "http://127.0.0.1:8000/research")


@cl.on_chat_start
async def on_chat_start():
    await cl.Message(
        content="Welcome to the Research Analyst. Ask me to research any topic and I'll dig in."
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        resp = await client.post(API_URL, json={"query": message.content})
        resp.raise_for_status()
        data = resp.json()

    insights = "\n".join(f"- {item}" for item in data.get("key_insights", []))
    cites = data.get("cites")

    content = f"### Key Insights\n{insights}" if insights else "No insights returned."
    if cites:
        content += f"\n\n**Sources:** {cites}"

    await cl.Message(content=content).send()
