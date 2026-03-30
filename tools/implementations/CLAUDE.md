# tools/implementations/ — Concrete Tool subclasses

## Rules

Every tool follows this exact four-part structure:
1. Define `XxxToolConfig(BaseModel)` with `enabled: bool = Field(default=True, ...)`
2. `registry.register("xxx_tool", XxxToolConfig)` at module level — discovery depends on this
3. Subclass `Tool` (from `tools.repo`) with `name`, `anthropic_schema`, `description`, `simple_description` class attributes
4. Implement `run(**params)` routing on `params.pop("operation")`

Per-user credentials via `UserCredentialService().get_credential(type, service_name)`. Raise on missing — never fall back to a default or env var.

User-scoped file storage: `data/users/{user_id}/tmp/{file_id}/{uuid4_hex}.bin` + `.meta` sidecar (`filename`, `mime_type`). Served by `/files/{file_id}` (download) or `/images/{file_id}` (inline).

Tools returning images use two special result-dict keys: `_content_blocks` (list of Anthropic content blocks — `LLMProvider` pops and passes natively) and `_image_artifact` (`{file_id, alt_text}` — orchestrator emits `![alt](/v0/api/images/{file_id})` to stream).

Every `anthropic_schema` parameter description is an LLM caller contract. Use exact token names, state co-dependencies inline, name the failure mode. No hedging, no internal jargon.

## Files

- `contacts_tool.py` — Contact CRUD, search, and group management; owns `contacts` SQLite schema
- `continuum_tool.py` — Conversation and segment operations (search, navigation) against the CNS continuum
- `domaindoc_tool.py` — Domain knowledge document management; always-active essential tool; `anthropic_schema` is a `@property` that builds a live catalog from SQLite at schema-read time; `request_create`/`request_delete` return UI guidance only (noops)
- `email_tool.py` — Email send/read via user-configured provider credential
- `forage_tool.py` — Speculative background context gathering; fire-and-forget trigger that dispatches `agents/forage.py` agent loop; two params (`query` + `context`) to launch, `dismiss_task_id` to clear results; publishes to `ForageTrinket`
- `imagegen_tool.py` — Image generation/refinement via Google Gemini with Chat-based lineage; `generate` opens a new session, `refine` replays full history, `publish` emits `_image_artifact`; per-user API key via `UserCredentialService('google_genai')`; images uploaded to Anthropic Files API uncompressed
- `invokeother_tool.py` — Meta-tool for on-demand loading of non-essential tools at runtime
- `kasa_tool.py` — TP-Link Kasa smart home device control
- `maps_tool.py` — Google Maps geocoding, places, and distance; lazy client init
- `memory_tool.py` — LT_Memory search, pin, touch, and manual create; `create_memory` queues to Valkey for deferred processing at segment collapse (no spaCy at init time)
- `pager_tool.py` — Lattice federation messaging
- `punchclock_tool.py` — Time tracking
- `reminder_tool.py` — Reminder scheduling and management
- `square_tool.py` — Square payment and POS integration
- `weather_tool.py` — Weather data retrieval
- `web_tool.py` — Web search (Kagi primary, DuckDuckGo fallback) and page scraping
- `schemas/contacts_tool.sql` — DDL for the contacts SQLite schema owned by `contacts_tool.py`
