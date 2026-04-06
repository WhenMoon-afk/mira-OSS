# agents/ — Autonomous sidebar agents

## Rules

Agents extend `SidebarAgent` (in `base.py`). The base class owns the LLM-in-a-loop mechanics: LLM init, tool schema assembly (always includes `sidebar_tool`), input sanitization (when `sanitize_untrusted_input=True`), message loop with heartbeat, tool execution, `complete_task` detection, trace capture, and completion publishing via `on_completion()`.

Implementations define: `agent_id`, `internal_llm_key`, `available_tools`, `get_agent_prompt(work_item)`, `build_initial_message()`. Override `on_completion()` to publish to a different trinket (see `ForageAgent`). Default agent prompts live in `config/prompts/agents/` as `.txt` files, loaded via `load_agent_prompt()` from `base.py`. Per-rule prompts override the default when `work_item.context['agent_prompt']` is set — the trigger populates this from the matched rule's `prompt` column. If multiple rules with different prompts match the same item, the trigger writes a `conflict` record to `sidebar_activity` and skips the item.

The base class injects `thread_id` into ALL `sidebar_tool` calls (scratchpad and completion) — thread identity is a system concern, never passed by the LLM. For `complete_task`, it also injects `interface_name`, `agent_id`, and `run_count`. Loop terminates when the LLM calls `complete_task`, which writes to `sidebar_activity` SQLite via UPSERT and exits.

Agents are spawned in background threads with `contextvars.copy_context()`. Two spawn paths:
1. **SidebarDispatcher** — polls registered `SidebarTrigger` instances on an APScheduler interval, spawns agents for new `WorkItem`s. Owns dedup via `sidebar_activity` SQLite + in-flight tracking. Triggers return all discovered items; the dispatcher decides what to act on.
2. **Direct invocation** — a tool (e.g. `ForageTool`) creates a `WorkItem` and calls `agent.run()` in a background thread.

### Dedup & Retry

Dedup is the dispatcher's responsibility, not the trigger's. The dispatcher checks `sidebar_activity` for prior runs and uses `_dispatch_decision()` to determine: first dispatch, retry (if `max_retries > 0` and `run_count` allows), or skip.

For retries, the dispatcher sets `work_item.context['prior_run']` with the previous activity record. The base class calls `build_recovery_context(prior_run)` and prepends the result to the initial message. Override `build_recovery_context()` (default returns `None`) to inject failure-aware context.

Old `sidebar_activity` records and their scratchpad notes are cleaned up after 30 days (`_CLEANUP_RETENTION_DAYS`), rate-limited to once per 24h per user.

## Files

- `base.py` — `SidebarAgent` ABC. Shared loop mechanics, `sanitize_untrusted_input` flag for pre-loop injection defense, `ACTIVITY_TABLE_DDL` (with `run_count` column), `ensure_activity_schema()` (creates table + runs migrations), trace TypedDicts (`ToolCallTrace`, `IterationTrace`, `AgentTrace`). Exports `load_agent_prompt()` for loading prompts from `config/prompts/agents/`.
- `sidebar.py` — `WorkItem` model, `SidebarTrigger` protocol (`on_dispatched` for side effects, not dedup), `SidebarDispatcher` (APScheduler poll loop with SQLite-backed dedup, in-flight tracking, retry support, cleanup).
- `triggers/imap_trigger.py` — `ImapTrigger`: polls IMAP for emails matching per-user trigger rules. Discovery only — dedup handled by dispatcher. Returns raw content in WorkItem. Injection defense runs at the agent boundary via `sanitize_untrusted_input`. Sets `$MiraHandled` IMAP flag via `on_dispatched()`.
- `implementations/email_sidebar.py` — `EmailSidebarAgent`: handles emails per per-rule prompt (falls back to generic `email_sidebar_system.txt` if no rule prompt). Sets `sanitize_untrusted_input=True` for injection defense. `max_retries=1` with `build_recovery_context()` override. Tools: `email_tool`.
- `implementations/forage_agent.py` — `ForageAgent`: background research. Overrides `on_completion()` to publish to `ForageTrinket`. Tools: `continuum_tool`, `memory_tool`, `web_tool`.
