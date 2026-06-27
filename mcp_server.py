import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from tavily import TavilyClient

load_dotenv()

mcp = FastMCP("ResearchMCP")

_tavily: TavilyClient | None = None


def _client() -> TavilyClient:
    global _tavily
    if _tavily is None:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError("TAVILY_API_KEY is not set.")
        _tavily = TavilyClient(api_key=api_key)
    return _tavily


@mcp.tool()
def search_web(topic: str) -> str:
    """Search the web for a topic and return a short list of results.

    Args:
        topic: The topic or question to search for.
    """
    topic = topic.strip()
    if not topic:
        return "Please provide a topic to search for."

    response = _client().search(query=topic, max_results=3, include_answer=True)
    results = response.get("results", [])

    lines: list[str] = []
    for item in results:
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        content = (item.get("content") or "").strip()
        if not title and not content:
            continue
        lines.append(f"{title} -> {url}\n{content}")

    if not lines:
        return f"No search results were found for '{topic}'."

    answer = (response.get("answer") or "").strip()
    body = "\n\n".join(lines)
    if answer:
        return f"Summary: {answer}\n\n{body}"
    return body


app = mcp.streamable_http_app()
