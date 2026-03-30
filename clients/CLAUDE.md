# clients/ — External infrastructure clients and service adapters

## Rules

All secrets come from Vault via `get_database_url()`, `get_api_key()`, or `get_service_config(field)`. `VaultClient` is the only place env vars (`VAULT_ADDR`, `VAULT_ROLE_ID`, `VAULT_SECRET_ID`) are the primary config source — all other clients delegate to it.

Most clients are module-level singletons accessed through factory functions (`get_valkey()`, `get_hybrid_embeddings_provider()`, `get_lattice_client()`). `LLMProvider` is **not** a singleton — instantiate per use. `FilesManager` is **not** a singleton — requires a live `anthropic.Anthropic` instance.

All LLM calls in application code go through `LLMProvider.generate_response()` or `LLMProvider.stream_events()`. Never instantiate `GenericOpenAIClient` directly.

`internal_llm='purpose'` is the single source of truth for LLM-tuning params (model, max_tokens, effort, endpoint). Callers pass a purpose key; explicit overrides (`effort`, `thinking_tokens`, `endpoint_url`, `model_override`) take precedence.

`SQLiteClient` has no RLS. Manual `user_id` filtering in queries is the only isolation mechanism — it is not redundant.

`PostgresClient` pools are class-level, keyed by database name. `admin=True` uses a separate `{name}_admin` pool with BYPASSRLS role.

## Files

- `vault_client.py` — Vault AppRole auth and secret retrieval; the only permitted source of credentials for all other clients. `preload_secrets()` bulk-loads at startup and raises `RuntimeError` on any failure.
- `postgres_client.py` — Pooled raw-SQL client with automatic RLS context (`SET app.current_user_id`) on connection checkout. All `execute_*` methods are monkey-patched by `utils/perf.py` when `mira.perf` logger is at INFO or DEBUG.
- `valkey_client.py` — Caching, sessions, and rate limiting. Exposes sync, async, and binary clients from a single module-level pool. Pings Valkey on construction — fails immediately if unreachable.
- `sqlite_client.py` — Per-user tool data storage. No pooling; fresh connection per request. Factory `get_sqlite_client(db_path, user_id)` is cached per `user_id:path`.
- `llm_provider.py` — Universal LLM entry point. Owns streaming events, tool execution with circuit breaker, prompt caching, billing integration, and Anthropic failover. Exports `ThinkingConfig`, `EFFORT_BUDGET_MAP`, `build_batch_params`, `ToolCall`, `ToolExecution`, `ToolExecutionResult`.
- `hybrid_embeddings_provider.py` — Local asymmetric embeddings (`mdbr-leaf-ir-asym`, 768-dim) with Valkey-backed cache. `encode_realtime()` for queries; `encode_deep()` for documents.
- `lattice_client.py` — Thin HTTP client for Lattice federation. Only consumed by `pager_tool`. Not exported from `__init__.py`.
- `files_manager.py` — Anthropic Files API upload/delete with segment-scoped cleanup. `delete_file()` logs warnings on 404 rather than raising (cleanup is best-effort). Not exported from `__init__.py`.
- `__init__.py` — Re-exports `HybridEmbeddingsProvider`, `get_hybrid_embeddings_provider`, `LLMProvider`, `PostgresClient`, `SQLiteClient`, `ValkeyClient`, `get_valkey`, `get_valkey_client`, and selected vault functions. `LatticeClient` and `FilesManager` are excluded — import directly.

## Wiring

`build_batch_params(purpose, system_prompt, messages, *, cache_ttl=None)` is the standard construction path for all Anthropic Batch API param dicts. Batch submission sites check `"api.anthropic.com" in endpoint_url` before calling it — non-Anthropic endpoints fall through to `generate_response(internal_llm=)`.

`LLMProvider._execute_with_tools()` propagates contextvars to `ThreadPoolExecutor` workers via `contextvars.copy_context()`. Any new threaded path in this file must do the same for RLS enforcement to hold.

Billing auto-resolves `pricing_key` from `(model, endpoint_url)` inside `generate_response()` — call sites do not pass `pricing_key`. Missing `(model, endpoint_url)` pair in user context raises `BillingConfigurationError`. No user context (startup/system calls) skips billing entirely.
