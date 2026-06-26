# 📦 Import Required Libraries
import asyncio
import os
from dotenv import load_dotenv
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams

from agents import (
    Agent,                           # 🤖 Core agent class
    Runner,                          # 🏃 Runs the agent
    AsyncOpenAI,                     # 🌐 OpenAI-compatible async client
    OpenAIChatCompletionsModel,     # 🧠 Chat model interface
    set_tracing_disabled,           # 🚫 Disable internal tracing/logging
)

# 🌿 Load environment variables from .env file
load_dotenv()

# 🚫 Disable tracing for clean output
set_tracing_disabled(disabled=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# 🌐 Initialize the AsyncOpenAI-compatible client with Gemini details
external_client: AsyncOpenAI = AsyncOpenAI(
    api_key=GEMINI_API_KEY,
    base_url=BASE_URL,
)

model: OpenAIChatCompletionsModel = OpenAIChatCompletionsModel(
    model="gemini-2.5-flash",        # ⚡ Fast Gemini model
    openai_client=external_client
)

# URL of our standalone MCP server
# FastMCP streamable_http_app mounts the MCP server under the '/mcp/' path.
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp/")

async def main():
    # 1) Configure parameters for the MCPServerStreamableHttp client
    mcp_params = MCPServerStreamableHttpParams(url=MCP_SERVER_URL)
    print(f"MCPServerStreamableHttpParams configured for URL: {MCP_SERVER_URL}")

    # 2) Create connection to the MCP server using streamable HTTP
    async with MCPServerStreamableHttp(params=mcp_params, name="ResearchMCPServerClient") as mcp_client:
        print(f"Connected to MCP server client: '{mcp_client.name}'")

        # 3) Create agent and register MCP servers
        agent: Agent = Agent(
            name="Researcher",  # 🧑‍💻 Agent's name
            instructions=(
                "You are an expert in research on specific topics. Your role is to search "
                "multiple sources for relevant information about the topics using MCP tools "
                "and your goal is to extract key insights from the information and present "
                "it clearly with citations."
            ),
            model=model,
            mcp_servers=[mcp_client]
        )
        print(f"Agent '{agent.name}' initialized.")

        # 4) Run the agent to query a topic (e.g. searching using the MCP search_web tool)
        topic = "Latest developments in Agentic AI"
        print(f"Asking agent: 'Research on: {topic}'...")
        
        try:
            result = await Runner.run(agent, f"Research on: {topic}")
            print("\n--- Agent Response ---")
            print(result.final_output)
        except Exception as e:
            print(f"An error occurred during execution: {e}")

if __name__ == "__main__":
    asyncio.run(main())

