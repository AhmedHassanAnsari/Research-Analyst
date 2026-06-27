import asyncio
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional
import httpx

load_dotenv()

from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams
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



from langfuse import get_client, observe, propagate_attributes

langfuse = get_client()

@observe(name="mcp_research")
async def run_research(topic: str) -> Output:
   

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
        

         try:
            result = await Runner.run(agent, f"Research on: {topic}")
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
