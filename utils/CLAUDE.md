# utils/ — Shared Utilities & Infrastructure

Cross-cutting utilities used throughout MIRA. Each module is self-contained with minimal dependencies on other utils.

## Files

- **`perf.py`** — Performance monitoring instrumentation. All perf logic lives here — nothing scattered through business files. Monkey-patches DB execute_* methods at startup via `install_db_instrumentation()`. Three-tier behavior gated by `mira.perf` logger: DEBUG (full query detail + N+1 detection), INFO (summary lines), WARNING+ (silent, zero overhead). Exports: `PerfMiddleware`, `register_perf_routes`, `install_db_instrumentation`, `perf_profile` decorator. See `docs/PERFORMANCE_MONITORING.md` for usage guide
- **`logging_config.py`** — Custom log levels, user context injection, colored terminal output, and Anthropic SDK request logging. TOAST level (60) is registered at interpreter startup via `deploy/_mira_log_levels.py` installed as a `.pth` site-package — `logging_config.py` imports `TOAST` from there, with an inline fallback for dev environments without the `.pth` installed. `UserContextFilter` automatically injects user_id from contextvar into all log records (formatted as `[user_id]` when present, empty when not). `ColoredFormatter` with color-coded levels, `setup_colored_root_logging()`. OSS contribution hint on ERROR+. `setup_anthropic_sdk_logging()` creates `logs/anthropic_sdk.log` with rotating file handler for SDK debug output. `instrument_anthropic_client(client)` attaches httpx response hooks that map each `req_*` ID to the last 500 chars of message content — grep the log file for a request ID to see what was sent
- **`user_context.py`** — Contextvar-based user identity management. `set_current_user_id()` / `get_current_user_id()` flow user context from API boundary through RLS enforcement. Also manages segment context, user preferences, and `InternalLLMConfig` (frozen dataclass: model, endpoint, api_key_name, max_tokens, effort) — the single source of truth for all internal LLM-tuning params, loaded at startup via `load_internal_llm_configs()`, resolved per-call via `get_internal_llm(purpose)`
- **`database_session_manager.py`** — `LTMemorySessionManager` singleton with `LTMemorySession` (user-scoped RLS) and `AdminSession` (cross-user BYPASSRLS). Connection pooling, transaction/savepoint support. execute_* methods are monkey-patched by `perf.py` at startup
- **`thread_monitor.py`** — `ThreadMonitor` for tracking active/stuck operations. `@monitored_operation` decorator, `MonitoredThreadPoolExecutor`, periodic monitoring. Thresholds: 30s slow, 300s stuck
- **`scheduled_task_monitor.py`** — `ScheduledTaskMonitor` for tracking scheduled job execution history, durations, failures, timeouts
- **`scheduler_service.py`** — APScheduler service wrapper for scheduled background tasks
- **`scheduled_tasks.py`** — Registration of all scheduled tasks (memory extraction, cleanup, etc.). Also exports `get_users_due_for_job(interval)` — the platform function for use-day scheduling via `MOD(cumulative_activity_days, interval) = 0`
- **`lt_memory_jobs.py`** — LT_Memory scheduled job registration (moved from `lt_memory/`). Day-interval jobs use `get_users_due_for_job()` for stateless use-day gating; calendar-based jobs (extraction retry, batch polling) run on fixed intervals
- **`timezone_utils.py`** — UTC-everywhere datetime utilities. Always use `utc_now()` instead of `datetime.now()`. Exports: `utc_now`, `format_utc_iso`
- **`distributed_lock.py`** — Valkey-backed distributed locking for cross-process coordination
- **`user_credentials.py`** — `UserCredentialService` for per-user credential storage via Vault
- **`user_activity.py`** — User activity tracking
- **`userdata_manager.py`** — Per-user data directory management
- **`tag_parser.py`** — Extracts structured tags from LLM responses (topic changes, memory signals, etc.)
- **`text_sanitizer.py`** — Text cleaning and sanitization utilities
- **`document_processing.py`** — Document parsing and text extraction
- **`image_compression.py`** — Image resizing/compression for uploads
- **`prompt_injection_defense.py`** — Input validation against prompt injection attacks
- **`http_client.py`** — Shared HTTP client utilities
- **`generic_openai_client.py`** — OpenAI-compatible API client (used by LLMProvider for failover)
- **`mcp_client.py`** — Model Context Protocol client integration
- **`playwright_service.py`** — Browser automation service for web tools
- **`synthetic_toolexample_generator.py`** — Generates synthetic tool usage examples for training

## Patterns to Follow

### Contextvar Usage
User identity flows via `utils.user_context` contextvars. Set once at API boundary, flows automatically through entire request. Use `contextvars.copy_context()` when spawning subthreads.

### Timezone
Always use `from utils.timezone_utils import utc_now` — never `datetime.now()` or `datetime.now(UTC)`.

### Performance Instrumentation
All perf code stays in `utils/perf.py`. If you add new database access classes with execute_* methods, add them to the `targets` list in `install_db_instrumentation()`. Do NOT add inline timing/logging to business logic files.
