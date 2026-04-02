# cns/services/ — Stateless service layer: orchestration, processing, and user model pipeline

## Rules

- No direct DB access. Services receive repositories via constructor injection and call repository methods only. SQL belongs in `cns/infrastructure/`.
- Prompts load from `config/prompts/` as `.txt` files in `__init__` or `_load_prompts()`. Never inline prompt strings as constants.
- `preprocess_content_blocks()` (from `cns.core.message`) is the canonical way to handle multimodal content (images, documents, tool results) before formatting for LLM input. Import it; don't re-implement truncation or media-block stripping.
- Non-critical fire-and-forget services (`peanutgallery_service`, feedback loops) swallow exceptions after logging. Critical-path services (`orchestrator`, `summary_generator`, `segment_collapse_handler`) let exceptions propagate.
- `force_immediate=True` on `collapse_segment()` skips batch scheduling — use it when memories must be ready before the user's next turn (e.g., the actions API). Default `force_immediate=False` routes through batch.

## Files

- `orchestrator.py` — Owns the message→LLM→response cycle: memory surfacing, system prompt composition, tool execution loop, context overflow remediation (embedding-based drift pruning then oldest-first fallback), and tool/thinking result persistence. Tool results are truncated at storage time via `_truncate_tool_result()` (config: `context.tool_result_max_chars`, default 100k chars) — JSON arrays are sliced to N complete elements, other formats get raw character truncation. Singleton via `get_orchestrator()`. Exports `TurnMetadata`, `LLMKwargs`, `ToolInteraction`.
- `subcortical.py` — Pre-LLM processing step. `generate()` returns `SubcorticalResult` (never None — raises on failure). Produces query expansion, named entity extraction, retention pin evaluation, and complexity assessment via `<query_expansion>`, `<entities>`, `<complexity>`, `<passage>` tags. Uses `internal_llm='analysis'`.
- `summary_generator.py` — Segment summary generation with thinking enabled and hierarchical chunking for oversized segments. Returns `SummaryResult(synopsis, display_title, complexity)`. Uses `internal_llm='summary'`. Imports `preprocess_content_blocks` from `cns.core.message`.
- `segment_collapse_handler.py` — Owns the `SegmentTimeoutEvent` response: sentinel lookup → summary → embedding → collapse → lt_memory extraction → portrait gate. `collapse_segment(event, force_immediate=False)` raises on failure; `handle_timeout` wraps it and swallows. Singleton via `get_segment_collapse_handler()`.
- `segment_helpers.py` — Pure utility functions for sentinel creation, collapse, display formatting, and marker creation. Canonical place for sentinel operations — never construct or parse sentinel Messages manually.
- `segment_timeout_service.py` — Scheduled admin-level job (every 5 min) that queries across all users for active segments (excludes paused) past timeout threshold and publishes `SegmentTimeoutEvent`. Returns `TimeoutCheckResult` TypedDict. Paused segments are invisible to this service — they never time out until the user resumes them (auto-resume on next message or explicit unpause).
- `assessment_extractor.py` — User model pipeline step 1. Evaluates conversation against anonymized system prompt sections, producing `AssessmentSignal` objects (`alignment`/`misalignment`/`contextual_pass`). Uses `internal_llm='assessment'`. Imports `TOOL_RESULT_TRUNCATION_LIMIT` and `_MEDIA_BLOCK_TYPES` from `cns.core.message` for conversation formatting.
- `user_model_synthesizer.py` — User model pipeline step 2. Synthesizes section-anchored observations from assessment signals with a Haiku critic validation loop (up to 3 attempts). Exports `UserObservation`, `CriticResult`, `SynthesisResult`. Uses `internal_llm='synthesis'` and `internal_llm='critic'`.
- `system_prompt_parser.py` — Pure utility: extracts section IDs, anonymizes system prompt XML, formats section lists. Used by `assessment_extractor` and `user_model_synthesizer`. No LLM calls.
- `peanutgallery_model.py` — Two-stage LLM pipeline (fast prerunner → Sonnet observer). Returns `PeanutGalleryResult` with action `noop`/`compaction`/`concern`/`coaching`. Imports `preprocess_content_blocks` from `cns.core.message` for multimodal formatting. Uses `internal_llm='analysis'` (prerunner) and `internal_llm='tidyup'` (observer).
- `peanutgallery_service.py` — Fire-and-forget async wrapper around `PeanutGalleryModel`. Subscribes to `TurnCompletedEvent`, runs every N turns via `ThreadPoolExecutor` with `contextvars.copy_context()`. Swallows exceptions.
- `memory_relevance_service.py` — Thin wrapper around `lt_memory.ProactiveService`. Validates 768d embedding, delegates search. Returns `list[MemoryDict]`.
- `portrait_service.py` — Synthesizes a prose user portrait (150–250 words) from collapsed segment summaries. Read-only at turn time via `read_portrait(user_id)`; synthesis triggered by segment collapse chain, gated by use-day modular arithmetic. Uses `internal_llm='portrait'`. Stores result on `users.portrait`.
- `manifest_query_service.py` — Segment data retrieval for manifest display. Valkey-cached with event-driven invalidation on `ManifestUpdatedEvent`. Singleton via `initialize_manifest_query_service()` / `get_manifest_query_service()` split. Exports `ManifestSegment` TypedDict.
- `domaindoc_summary_service.py` — One-sentence section summaries for DomainDoc via `internal_llm='analysis'`. Module-level singletons with lazy init.

## Wiring

Memory surfacing pipeline (inside `orchestrator.process_message()`): `subcortical.generate()` → pinned cap (`max_pinned_memories=15`) → fresh budget (`max(min_fresh, max_surfaced - pinned)`) → `memory_relevance_service` embedding search → merge → `UpdateTrinketEvent` to `ProactiveMemoryTrinket`. Linked memories capped at `max_linked_per_primary=2` and rendered as `<context>` annotations. Total bounded by `max_surfaced_memories=20`.

User model pipeline (triggered in segment collapse chain): `assessment_extractor.extract_signals()` produces `list[AssessmentSignal]` → `user_model_synthesizer.synthesize()` consumes signals → `system_prompt_parser` utilities provide anonymized prompt and section metadata to both steps.
