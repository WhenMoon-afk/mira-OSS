# cns/api/ — FastAPI routing layer: auth gate, input validation, delegate to services

## Rules

- Every protected route uses `Depends(get_current_user)` from `auth.api`. Set `set_current_user_id(user_id)` immediately inside the handler — before any service call. No exceptions.
- No business logic here. Handlers validate input, acquire the distributed lock if needed, call `orchestrator.process_message()` or a repository, then return. Logic belongs in `cns/services/` or tools.
- All responses go through `create_success_response()` / `create_error_response()` from `base.py`. HTTP status codes map: 400 → `ValidationError`, 402 → `InsufficientBalanceError`, 404 → `NotFoundError`, 503 → `ServiceUnavailableError`, 500 → unhandled.
- `UserRequestLock(ttl=60)` is module-level in both `chat.py` and `websocket_chat.py` — one lock instance per file, shared across requests. Do not instantiate per-request.
- WebSocket sync calls run via `run_in_threadpool(ctx.run, ...)` where `ctx = contextvars.copy_context()`. The `ctx.run` wrapper is required — threadpool drops contextvars otherwise.
- `InsufficientBalanceError` is conditionally imported (`try/except ImportError` → `None`) for OSS compatibility. Always guard with `if InsufficientBalanceError is not None and isinstance(e, InsufficientBalanceError)`.

## Files

- `base.py` — Owns `SuccessResponse`, `ErrorResponse`, `APIResponse`, `ErrorDetail`, `ResponseMeta`, the `APIError` hierarchy, `BaseHandler`, `create_success_response()`, and `create_error_response()`. All other files in this directory import from here.
- `chat.py` — `POST /chat`. Non-streaming HTTP chat. Owns two-tier image compression (1200px inference / 512px WebP storage) and document-to-`ContentBlock` assembly before handing to `orchestrator.process_message()`.
- `websocket_chat.py` — `WebSocket /ws/chat`. Streaming chat. Auth protocol: first message must be `{"type": "auth", "token": "..."}`. Owns partial-response persistence: if the orchestrator raises after text was already sent, the handler commits user + partial assistant messages with `metadata={"partial_response": True}`.
- `actions.py` — `POST /actions`. Domain-routed mutations via `DomainType` enum and `BaseDomainHandler` subclasses. Also owns `GET /tools/{tool_name}/query`. New domains require a handler class extending `BaseDomainHandler` and registration in `ActionsEndpoint`.
- `data.py` — `GET /data?type=...`. Read-only access routed by `DataType` enum (HISTORY, MEMORIES, DASHBOARD, USER, DOMAINDOCS, WORKING_MEMORY, LORA). Pagination via `offset`/`limit` query params.
- `files.py` — `GET /files/{file_id}` (download) and `GET /images/{file_id}` (inline). Serves `data/users/{user_id}/tmp/{file_id}/`. Security: `FILE_ID_PATTERN` regex + resolved-path-must-stay-within-base-dir check. `.meta` sidecar provides filename and media type.
- `health.py` — `GET /health`, `/health/threads`, `/health/thread-dump`. No auth. Owned by `ThreadMonitor` and `ScheduledTaskMonitor`.
- `tool_config.py` — CRUD for per-user tool configuration. Discovers configurable tools via `registry._registry`, stores config via `UserCredentialService`, validates against each tool's registered Pydantic schema.
- `location.py` — `POST /location`. Reverse geocodes via Nominatim, fetches 2-hour forecast from Open-Meteo, caches at `location:{user_id}` in Valkey (24h TTL). Also back-fills weather for gap days since last conversation.
- `demo.py` — `POST /demo/session`, `POST /demo/chat`. Ephemeral demo sessions in Valkey (15 min TTL, 5 msg/min rate limit). Self-contained — excluded from OSS builds via `makeoss.sh`.
- `federation.py` — `POST /federation/deliver`. Lattice server-to-server webhook. No user auth (Lattice handles verification). Delivers inbound federated messages via `PagerTool`.
- `update.py` — `GET /check_update`. No auth. Compares semver against `/VERSION` file; logs checks to `data/update_checks.log`.
- `oss_ui.py` — `GET /chat`, `GET /`, `GET /oss-assets/*`. Self-contained minimal chat UI for OSS builds. Reads HTML and vendored JS from `deploy/oss_ui/` at import time, serves from memory. Only mounted when `web/chat/` is absent (conditional in `main.py`). No auth dependency — the HTML handles Bearer token via localStorage.
