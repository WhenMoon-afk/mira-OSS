# agents/ — Background agent modules

## Rules

Agents are LLM-in-a-loop modules activated by tools. Each agent receives a task from the calling tool, uses ToolRepository tools to gather information, and publishes results to a trinket via EventBus. Agents run in background threads with copied user context (`contextvars.copy_context()`).

Agent modules export a `run()` function as their entry point. The calling tool handles thread spawning, context propagation, and event bus access — the agent module focuses on the loop logic.

Agents use the standard ToolRepository for tool access to avoid maintaining parallel search implementations. Tool schemas are extracted from the repository at runtime.

## Files

- `forage.py` — Background research agent for speculative context gathering. Loop: receives query + context, searches via continuum_tool/memory_tool/web_tool, produces written briefing. Heartbeat is "Continue." user message. Quality rubric gates output. Activated by `tools/implementations/forage_tool.py`, publishes to `ForageTrinket`.
