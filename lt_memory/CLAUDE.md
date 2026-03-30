# lt_memory/ — Long-term memory: extraction, linking, consolidation, and retrieval

## Rules

- `LTMemoryFactory` is the sole constructor for all services here — never instantiate `LTMemoryDB`, `VectorOps`, `LinkingService`, etc. directly outside tests. Access the singleton via `get_lt_memory_factory()`.
- `BatchCoordinator.submit_batch()` is the only path for submitting batches to Anthropic. No direct `anthropic_client.beta.messages.batches.create()` calls elsewhere in this directory.
- Callers store `input_data` in their own batch records (`create_extraction_batch()` or `create_post_processing_batch()`) before calling `submit_batch()` — `submit_batch()` does not accept `input_data`.
- `BatchKind` (`"extraction"` | `"post_processing"`) discriminates all generic batch DB methods. Use it; don't duplicate per-kind SQL.
- All shared types cross-used across files live in `models.py`. File-local types (e.g., `EntityNode`, `EntityGCDecision` in `entity_gc.py`) stay in their file. `ProcessingChunk.messages` stays `List[Any]` — Pydantic can't resolve TYPE_CHECKING-only imports at runtime.
- `factory.immediate_strategy` bypasses batch submission and is reserved for manual collapse only (segment collapse must complete before the user's next conversation).

## Files

- `models.py` — All Pydantic models and shared TypedDicts. Source of truth for `Memory`, `ExtractedMemory`, `MemoryLink`, `Entity`, `ExtractionBatch`, `PostProcessingBatch`, `ProcessingChunk`, `ConsolidationCluster`, `PendingManualMemory`, and the 18 cross-file TypedDicts. Literal aliases: `RelationshipType`, `BatchStatus`, `BatchKind`.
- `db_access.py` — All SQL for memories, entities, batches, and scoring. Loads scoring formula from `scoring_formula.sql` at import time. Uses `LTMemorySessionManager` for RLS-scoped connections. `get_memories_by_segment_id(segment_id)` traces memories back to their source segment (uses partial index `idx_memories_source_segment_id`).
- `scoring_formula.sql` — SQL expression for importance score recalculation, loaded by `db_access.py`. Edit here, not inline.
- `factory.py` — Creates and wires all service instances in dependency order with reverse-order cleanup. Singleton via `get_lt_memory_factory()`.
- `vector_ops.py` — Embedding generation and vector similarity search using mdbr-leaf-ir-asym (768d). Owns `HybridSearcher` composition.
- `hybrid_search.py` — BM25 + vector hybrid search with reciprocal rank fusion. `HybridSearcher.hybrid_search()` returns `List[Memory]`.
- `linking.py` — Three-axis candidate discovery (vector similarity, entity co-occurrence with similarity floor, TF-IDF term overlap) and bidirectional link creation. TF-IDF state lazily initialized on `LinkingService`, rebuilt when memory count changes. `classify_relationship_sync()` and `_parse_classification_response()` have no active callers (dead code).
- `proactive.py` — Proactive memory surfacing: merges similarity pool and hub-derived pool, reranks with link traversal. Returns `List[MemoryDict]`.
- `hub_discovery.py` — Entity-driven retrieval: pg_trgm fuzzy entity match → linked memories → expansion-similarity ranking. DB errors propagate from `_match_entities()`.
- `refinement.py` — Consolidation cluster identification via connected-components and payload building for batch consolidation.
- `entity_extraction.py` — spaCy NER (en_core_web_lg, parser/lemmatizer disabled) with fuzzy normalization. Returns `List[NamedEntity]`.
- `entity_gc.py` — Entity deduplication: pg_trgm self-join → BFS grouping → Anthropic Batch API review → merge/delete/keep execution. File-local types: `EntityNode`, `EntityGCDecision`, `ReviewPrompt`.
- `memory_formatter.py` — XML formatting of memories and annotations for prompt inclusion.
- `batch_result_handlers.py` — `BatchResultProcessor` implementations for extraction, relationship classification, consolidation, and entity GC. `PostProcessingBatchDispatcher` routes by batch type.
- `__init__.py` — Public re-exports for all shared models and types.
- `processing/` — Extraction and post-processing pipeline (see `processing/CLAUDE.md`).
