import html
import re
import sys
from urllib.parse import quote_plus

import requests
from mcp.server.fastmcp import FastMCP

server = FastMCP(
    "ResearchMCP",
    instructions="A simple MCP server that can search the web for a topic and return useful results.",
)


@server.tool()
def search_web(topic: str) -> str:
    """Search the web for a topic and return a short list of results.

    Args:
        topic: The topic or question to search for.
    """
    topic = topic.strip()
    if not topic:
        return "Please provide a topic to search for."

    search_url = f"https://duckduckgo.com/html/?q={quote_plus(topic)}"
    response = requests.get(
        search_url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10,
    )
    response.raise_for_status()

    matches = re.findall(r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>', response.text, re.S)
    results: list[str] = []
    for href, title in matches[:5]:
        cleaned_title = re.sub(r"<.*?>", "", title)
        cleaned_title = html.unescape(cleaned_title).strip()
        if cleaned_title:
            results.append(f"{cleaned_title} -> {href}")

    if not results:
        return f"No search results were found for '{topic}'."

    return "\n".join(results)

server=server.streamable_http_app();
