# Project Agent Rules

This project is built around the following stack:
- Python
- OpenAI Agents SDK
- Model Context Protocol (MCP)
- uv for dependency and environment management
- FastAPI for APIs
- Chainlit for UI
- Langfuse for observability
- Docker and Kubernetes for local deployment
- Helm for Kubernetes manifests

## Core Rules
1. Prefer Python 3.11+ idioms and type hints in all new code.
2. Use uv for installing and managing dependencies.
   - Add packages with: `uv add <package>`
   - Run scripts with: `uv run <command>`
3. Keep the architecture modular:
   - Use FastAPI for backend endpoints and services.
   - Use Chainlit for conversational UI flows.
   - Use the OpenAI Agents SDK for agent orchestration.
   - Use MCP for tool and context integrations.
4. Keep configuration environment-driven:
   - Use environment variables for secrets and runtime settings.
   - Avoid hardcoding API keys or sensitive values.
5. Containerize changes thoughtfully:
   - Ensure Docker images remain minimal and reproducible.
   - Keep Kubernetes deployment manifests aligned with Helm values.
6. Prefer clear, maintainable code:
   - Follow small, focused functions and classes.
   - Add docstrings and comments only where they improve clarity.
   - Write tests for non-trivial behavior.

## Development Expectations
- Before making changes, inspect the existing structure and follow the current patterns.
- Keep changes scoped and avoid unrelated refactors.
- When introducing new dependencies, update the project configuration and document the reason.
- Prefer simple, robust solutions over overly clever implementations.
