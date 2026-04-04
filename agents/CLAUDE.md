# agents/ — Autonomous sidebar agents

## Rules

Agents extend `SidebarAgent` (in `base.py`). The base class owns the LLM-in-a-loop mechanics: LLM init, tool schema assembly (always includes `sidebar_tool`), message loop with heartbeat, tool execution, `complete_task` detection, trace capture, and completion publishing via `on_completion()`.

Implementations define: `agent_id`, `internal_llm_key`, `available_tools`, `get_agent_prompt()`, `build_initial_message()`. Override `on_completion()` to publish to a different trinket (see `ForageAgent`).

The base class injects `thread_id` into ALL `sidebar_tool` calls (scratchpad and completion) — thread identity is a system concern, never passed by the LLM. For `complete_task`, it also injects `interface_name` and `agent_id`. Loop terminates when the LLM calls `complete_task`, which writes to `sidebar_activity` SQLite and exits.

Agents are spawned in background threads with `contextvars.copy_context()`. Two spawn paths:
1. **SidebarDispatcher** — polls registered `SidebarTrigger` instances on an APScheduler interval, spawns agents for new `WorkItem`s.
2. **Direct invocation** — a tool (e.g. `ForageTool`) creates a `WorkItem` and calls `agent.run()` in a background thread.

## Files

- `base.py` — `SidebarAgent` ABC. Shared loop mechanics, `ACTIVITY_TABLE_DDL`, trace TypedDicts (`ToolCallTrace`, `IterationTrace`, `AgentTrace`).
- `sidebar.py` — `WorkItem` model, `SidebarTrigger` protocol, `SidebarDispatcher` (APScheduler poll loop).
- `triggers/imap_trigger.py` — `ImapTrigger`: polls IMAP for emails from configured senders, dedup via Valkey, sanitizes content through `PromptInjectionDefense` with `require_llm_detection=True`. Sets `$MiraHandled` IMAP flag on processed messages.
- `implementations/email_sidebar.py` — `EmailSidebarAgent`: handles RCWC contact form emails per business rubric. Tools: `email_tool`.
- `implementations/forage_agent.py` — `ForageAgent`: background research. Overrides `on_completion()` to publish to `ForageTrinket`. Tools: `continuum_tool`, `memory_tool`, `web_tool`.
