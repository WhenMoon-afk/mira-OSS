# config/ — Application configuration and system prompt template

## Rules

- All settings are Pydantic `BaseModel` schemas with hardcoded defaults in `config.py`. No required fields — the system must boot with zero external input.
- Secrets (API keys, DB URLs) are never stored here. They are lazy Vault lookups via properties on `AppConfig` (e.g., `config.api_key` calls `get_api_key(self.api.api_key_name)`). No env-var fallbacks.
- The `config` singleton is module-level state created at import time: `config = initialize_config()` in `config_manager.py`. Import it as `from config import config`. Never instantiate `AppConfig` directly in application code.
- `__init__.py` imports `tools.registry` before `config_manager` — this import order is load-bearing for circular dependency avoidance. Do not reorder.
- `config.<tool_name>_tool` triggers `AppConfig.__getattr__` → `get_tool_config()` → `registry.get_or_create()`. This is the only correct way to access tool configs.
- `ScheduledJobsConfig` fields ending in `_use_days` are modular activity-day intervals, not calendar intervals. `consolidation_use_days=7` means "run when `MOD(cumulative_activity_days, 7) = 0`", not "run every 7 calendar days".
- `system_prompt.txt` is loaded once at startup by `AppConfig._load_system_prompt()`. Template variables `{first_name}`, `{user_context}`, and `{relative time since account creation}` are substituted by `working_memory/core.py`, not by config.

## Files

- `config.py` — Pure Pydantic schema definitions for every config section (`ApiConfig`, `LTMemoryConfig`, `ScheduledJobsConfig`, `SystemConfig`, `SidebarDispatcherConfig`, `ImapTriggerConfig`, etc.). `ImapTriggerConfig` controls whether IMAP polling is active and the discovery time window; which emails to act on is per-user via `trigger_rules` in the user's SQLite DB. `SystemConfig` includes two-tier session cache settings: `session_summary_complexity_limit` (Tier 1 extended), `session_precis_max_count` (Tier 2 precis). No logic, no side effects.
- `config_manager.py` — `AppConfig` (root aggregate), `initialize_config()`, and the `config` singleton. Owns Vault property lookups and dynamic tool config via `__getattr__`.
- `__init__.py` — Re-exports `config` and `AppConfig`; enforces registry-before-config import order.
- `system_prompt.txt` — Mira's core identity prompt. Section order is semantics: foundational identity appears before behavioral directives because earlier tokens condition interpretation of later ones.
- `announcement.py` — Module-level cache for `announcement.json`. `load_announcement()` called once at startup lifespan; `get_cached_announcement()` used by `cns/api/data.py`.
- `announcement.json` — Active announcement state. Set `id` + `message` to show banner; set both to `null` to suppress. Requires app restart to take effect.
- `announcement.sample.json` — Reference format for `announcement.json`.
- `vault.hcl` — Local dev Vault server config (file storage, `127.0.0.1:8200`, no TLS). Consumed by the Vault binary, not Python.
- `prompts/` — LLM prompt templates for all subsystems. See `prompts/CLAUDE.md`.
