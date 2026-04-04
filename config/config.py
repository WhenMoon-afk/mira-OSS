"""
Base schema definitions for configuration models.

These are the core schema models used throughout the application to
ensure type safety and validation of configuration values.
"""

from typing import Optional, List

from pydantic import BaseModel, Field

class ApiConfig(BaseModel):
    """Anthropic API configuration settings."""

    # API key configuration
    api_key_name: str = Field(default="anthropic_key", description="Name of the Anthropic API key to retrieve from Vault")

    # Generation settings
    model: str = Field(default="claude-sonnet-4-6", description="Default Anthropic model for LLM calls when no tier/override is specified")
    max_tokens: int = Field(default=10000, description="Maximum number of tokens to generate in responses")
    context_window_tokens: int = Field(default=200000, description="Total context window size in tokens for the model")
    temperature: float = Field(default=1.0, description="Temperature setting for response generation (Anthropic default: 1.0)")

    # Request settings
    timeout: int = Field(default=60, description="Request timeout in seconds")

    # Emergency fallback settings (defaults to local Ollama - no API key required)
    emergency_fallback_enabled: bool = Field(default=True, description="Enable automatic failover to emergency provider on Anthropic errors")
    emergency_fallback_endpoint: str = Field(default="http://localhost:11434/v1/chat/completions", description="OpenAI-compatible endpoint for emergency fallback (default: local Ollama)")
    emergency_fallback_api_key_name: Optional[str] = Field(default=None, description="Vault key name for emergency fallback API key (None for local providers like Ollama)")
    emergency_fallback_model: str = Field(default="qwen3:1.7b", description="Model to use during emergency fallback")
    emergency_fallback_recovery_minutes: int = Field(default=5, description="Minutes to wait before testing Anthropic recovery")

    # Generic provider thinking display
    show_generic_thinking: bool = Field(default=True, description="Show thinking blocks from generic providers to end user")

    # Subcortical layer settings (query expansion for memory retrieval)
    analysis_enabled: bool = Field(default=True, description="Enable subcortical layer for retrieval")

class ApiServerConfig(BaseModel):
    """FastAPI server configuration settings."""
    
    host: str = Field(default="0.0.0.0", description="Host address for the FastAPI server")
    port: int = Field(default=1993, description="Port for the FastAPI server")
    workers: int = Field(default=1, description="Number of uvicorn workers")
    log_level: str = Field(default="warning", description="Log level for uvicorn server")
    enable_cors: bool = Field(default=True, description="Enable CORS middleware")
    cors_origins: List[str] = Field(
        default=["https://miraos.org", "http://localhost:1993", "http://127.0.0.1:1993"],
        description="Allowed CORS origins (production and local development)"
    )
    extended_thinking: bool = Field(default=False, description="Whether to enable extended thinking capability")
    extended_thinking_budget: int = Field(default=1024, description="Token budget for extended thinking when enabled (min: 1024)")


class ToolConfig(BaseModel):
    """Tool-related configuration settings."""

    essential_tools: List[str] = Field(
        default=["web_tool", "invokeother_tool", "continuum_tool", "reminder_tool", "memory_tool", "domaindoc_tool", "forage_tool", "sidebaragents_tool"],
        description="List of essential tools (warns if disabled)"
    )

class EmbeddingsFastModelConfig(BaseModel):
    """Embedding model configuration."""

    cache_dir: Optional[str] = Field(default=None, description="Cache directory for model files")
    batch_size: int = Field(default=32, description="Batch size for encoding")

class EmbeddingsConfig(BaseModel):
    """Embeddings provider configuration settings."""

    provider: str = Field(default="hybrid", description="Embeddings provider: 'hybrid' for dual-model system")

    # Model configurations
    fast_model: EmbeddingsFastModelConfig = Field(default_factory=EmbeddingsFastModelConfig, description="Embedding model configuration (mdbr-leaf-ir-asym)")

class SystemConfig(BaseModel):
    """System-level configuration settings."""

    log_level: str = Field(default="WARNING", description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    timezone: str = Field(default="America/Chicago", description="Default timezone for date/time operations (must be a valid IANA timezone name like 'America/New_York', 'Europe/London')")

    # Segment Timeout Threshold (minutes)
    # NOTE: Can be made context-aware by time of day if needed in the future
    # (e.g., shorter timeout during morning hours, longer during late night)
    segment_timeout: int = Field(default=60, description="Segment collapse timeout in minutes (60 minutes)")

    # Manifest Display Settings
    manifest_depth: int = Field(default=15, description="Number of recent segments to include in manifest display")
    manifest_cache_ttl: int = Field(default=3600, description="TTL for manifest cache in seconds (1 hour default)")

    # Session Cache Settings (Two-Tier Complexity-Based Loading)
    session_summary_complexity_limit: float = Field(
        default=4.5,
        description="Maximum total complexity score for Tier 1 extended summaries"
    )
    session_summary_max_count: int = Field(
        default=4,
        description="Maximum number of Tier 1 extended summaries regardless of complexity"
    )
    session_summary_query_window: int = Field(
        default=14,
        description="Number of recent segments to query for two-tier selection"
    )
    session_precis_max_count: int = Field(
        default=4,
        description="Maximum number of Tier 2 precis-only summaries to load after extended summaries"
    )


# ============================================================================
# LT_Memory Configuration
# ============================================================================

class ExtractionConfig(BaseModel):
    """
    Extraction service configuration.

    Controls memory extraction behavior and LLM parameters.
    """
    dedup_similarity_threshold: float = Field(
        default=0.92,
        ge=0.0,
        le=1.0,
        description="Cosine similarity threshold for duplicate detection"
    )
    default_importance_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Default importance score for newly extracted memories"
    )


class BatchingConfig(BaseModel):
    """
    Batching orchestration configuration.

    Controls batch submission and processing behavior.
    """
    api_key_name: str = Field(
        default="anthropic_batch_key",
        description="Vault key name for Anthropic Batch API (separate from chat to isolate rate limits and costs)"
    )
    batch_expiry_hours: int = Field(
        default=24,
        description="Hours before Anthropic batch expires"
    )
    max_retry_count: int = Field(
        default=3,
        description="Maximum retry attempts for failed batch processing before permanent failure"
    )
    # Batch processing timeouts and limits
    batch_max_age_hours: int = Field(
        default=48,
        description="Maximum age in hours for batches to poll (Anthropic results expire after 24h)"
    )
    batch_processing_timeout_seconds: int = Field(
        default=300,
        description="Maximum seconds to spend processing a single batch result (5 minutes)"
    )
    max_batches_per_poll: int = Field(
        default=3,
        description="Maximum Anthropic batch IDs to process per poll cycle (prevents timeout when many batches accumulate)"
    )


class LinkingConfig(BaseModel):
    """
    Linking service configuration.

    Controls relationship classification and link management.
    """
    similarity_threshold_for_linking: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Minimum similarity to consider for relationship classification"
    )
    max_candidates_per_memory: int = Field(
        default=20,
        description="Maximum candidate memories to evaluate for links"
    )
    max_link_traversal_depth: int = Field(
        default=3,
        description="Maximum depth for link traversal when navigating memory graph"
    )
    classification_max_tokens: int = Field(
        default=500,
        description="Maximum tokens for relationship classification LLM calls"
    )
    entity_similarity_floor: float = Field(
        default=0.55,
        ge=0.0,
        le=1.0,
        description="Minimum embedding cosine similarity for entity co-occurrence candidates (filters O(N²) entity noise)"
    )
    tfidf_similarity_threshold: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Minimum TF-IDF cosine similarity for term-based candidate discovery (rescues orphan memories with no entities)"
    )
    tfidf_max_candidates: int = Field(
        default=10,
        description="Maximum candidates returned by TF-IDF discovery axis per source memory"
    )


class RefinementConfig(BaseModel):
    """
    Refinement service configuration.

    Controls memory consolidation behavior.
    """
    consolidation_similarity_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for considering consolidation"
    )
    min_cluster_size: int = Field(
        default=2,
        description="Minimum memories in cluster for consolidation"
    )
    max_consolidation_rejection_count: int = Field(
        default=3,
        description="Number of consolidation rejections before memory is excluded from future consolidation candidates"
    )


class ProactiveConfig(BaseModel):
    """
    Proactive surfacing configuration.

    Controls memory surfacing behavior for CNS integration.
    """
    similarity_threshold: float = Field(
        default=0.42,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity for surfacing memories"
    )
    max_link_traversal_depth: int = Field(
        default=3,
        description="Maximum depth for link traversal when expanding context"
    )
    max_memories: int = Field(
        default=10,
        description="Maximum memories to return per search"
    )
    min_importance_score: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Minimum importance score for surfacing"
    )
    max_surfaced_memories: int = Field(
        default=20,
        description="Maximum total primary memories in context window (pinned + fresh)"
    )
    max_pinned_memories: int = Field(
        default=15,
        description="Hard cap on retained memories from previous turn"
    )
    min_fresh_memories: int = Field(
        default=5,
        description="Guaranteed minimum fresh retrieval slots"
    )
    max_linked_per_primary: int = Field(
        default=2,
        description="Maximum linked memories displayed per primary memory"
    )

    # Debut boost: temporary ranking boost for new memories before they build hub connections
    debut_full_boost_days: int = Field(
        default=7,
        description="Full debut boost for days 0-6 (activity days, not calendar)"
    )
    debut_end_days: int = Field(
        default=10,
        description="Debut boost trails off completely by this day"
    )
    debut_boost_amount: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Maximum debut boost amount (added to importance score)"
    )
    hub_connection_threshold: int = Field(
        default=2,
        description="Entity link count at which memory no longer needs debut boost"
    )

    # Supersedes penalty for soft demotion of superseded memories
    supersedes_penalty_multiplier: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Score multiplier for memories with inbound supersedes links (0.3 = 70% reduction)"
    )

    # Link type weights for reranking (higher = more important)
    link_weight_conflicts: float = Field(default=1.0, description="Weight for 'conflicts' links")
    link_weight_corroborates: float = Field(default=0.9, description="Weight for 'corroborates' links")
    link_weight_supersedes: float = Field(default=0.9, description="Weight for 'supersedes' links")
    link_weight_refines: float = Field(default=0.8, description="Weight for 'refines' links")
    link_weight_precedes: float = Field(default=0.7, description="Weight for 'precedes' links")
    link_weight_contextualizes: float = Field(default=0.7, description="Weight for 'contextualizes' links")
    link_weight_exemplifies: float = Field(default=0.75, description="Weight for 'exemplifies' links")
    link_weight_shares_entity: float = Field(default=0.4, description="Weight for 'shares_entity' links")
    link_weight_default: float = Field(default=0.5, description="Weight for unknown link types")
    # Importance inheritance formula: (linked * weight) + (primary * (1-weight))
    link_importance_inheritance_weight: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Weight for linked memory importance (primary gets 1 - this value)"
    )

    # Parallel execution settings
    search_max_workers: int = Field(
        default=2,
        description="Thread pool size for parallel similarity/hub searches"
    )
    search_oversample_factor: int = Field(
        default=2,
        description="Multiplier for oversampling before filtering"
    )


class VectorSearchConfig(BaseModel):
    """
    Vector search configuration.

    Default parameters for similarity search operations across the system.
    """
    default_similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Default cosine similarity threshold for vector searches"
    )
    default_limit: int = Field(
        default=10,
        description="Default maximum results for vector searches"
    )


class HybridSearchConfig(BaseModel):
    """
    Hybrid search configuration.

    Controls BM25/vector fusion weights and scoring parameters.
    """
    default_limit: int = Field(
        default=20,
        description="Default maximum results for hybrid search"
    )
    default_similarity_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Default similarity threshold for hybrid search"
    )
    default_min_importance: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Default minimum importance for hybrid search"
    )
    oversample_multiplier: int = Field(
        default=2,
        description="Multiplier for oversampling before fusion (e.g., 2x limit)"
    )

    # Intent-based weights: (bm25_weight, vector_weight)
    intent_recall_bm25: float = Field(default=0.6, description="BM25 weight for 'recall' intent")
    intent_recall_vector: float = Field(default=0.4, description="Vector weight for 'recall' intent")
    intent_explore_bm25: float = Field(default=0.3, description="BM25 weight for 'explore' intent")
    intent_explore_vector: float = Field(default=0.7, description="Vector weight for 'explore' intent")
    intent_exact_bm25: float = Field(default=0.8, description="BM25 weight for 'exact' intent")
    intent_exact_vector: float = Field(default=0.2, description="Vector weight for 'exact' intent")
    intent_general_bm25: float = Field(default=0.4, description="BM25 weight for 'general' intent")
    intent_general_vector: float = Field(default=0.6, description="Vector weight for 'general' intent")

    # Reciprocal Rank Fusion parameters
    rrf_k: int = Field(
        default=60,
        description="Constant k for reciprocal rank fusion formula"
    )


class ScheduledJobsConfig(BaseModel):
    """
    Scheduled job intervals configuration.

    Controls timing for background maintenance tasks.
    """
    extraction_retry_hours: int = Field(
        default=6,
        description="Hours between failed extraction retries"
    )
    batch_poll_minutes: int = Field(
        default=1,
        description="Minutes between batch API polling (Anthropic recommends 1 minute)"
    )
    consolidation_use_days: int = Field(
        default=7,
        description="Use-days between consolidation (runs when MOD(cumulative_activity_days, interval) = 0)"
    )
    temporal_score_recalc_use_days: int = Field(
        default=1,
        description="Use-days between temporal score recalculations (runs when MOD(cumulative_activity_days, interval) = 0)"
    )
    bulk_score_recalc_use_days: int = Field(
        default=1,
        description="Use-days between bulk score recalculations (runs when MOD(cumulative_activity_days, interval) = 0)"
    )
    entity_gc_use_days: int = Field(
        default=7,
        description="Use-days between entity garbage collection (runs when MOD(cumulative_activity_days, interval) = 0)"
    )
    job_timeout_seconds: int = Field(
        default=120,
        description="Timeout for batch polling job monitors"
    )
    batch_cleanup_use_days: int = Field(
        default=1,
        description="Use-days between batch cleanup (runs when MOD(cumulative_activity_days, interval) = 0)"
    )
    portrait_synthesis_use_days: int = Field(
        default=10,
        description="Use-days between portrait synthesis (runs in segment collapse chain when MOD(cumulative_activity_days, interval) = 0)"
    )


class EntityGarbageCollectionConfig(BaseModel):
    """
    Entity garbage collection configuration.

    Controls pg_trgm similarity threshold for finding duplicate entity pairs
    and LLM review parameters. The GC flow: find similar pairs via self-join,
    group via BFS connected-components, batch LLM review for per-entity decisions.
    """
    similarity_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description=(
            "pg_trgm similarity threshold for entity name matching. "
            "Calibrated from production data (887 entities): 0.6 yields ~408 pairs. "
            "Catches same-name-different-type, spelling variations, possessives, prefix noise"
        )
    )


class LTMemoryConfig(BaseModel):
    """
    Complete LT_Memory system configuration.

    Aggregates all module-specific configs into single source of truth.
    Note: Scoring constants are hardcoded in lt_memory/scoring_formula.sql
    """
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    batching: BatchingConfig = Field(default_factory=BatchingConfig)
    linking: LinkingConfig = Field(default_factory=LinkingConfig)
    refinement: RefinementConfig = Field(default_factory=RefinementConfig)
    proactive: ProactiveConfig = Field(default_factory=ProactiveConfig)
    entity_gc: EntityGarbageCollectionConfig = Field(default_factory=EntityGarbageCollectionConfig)
    vector_search: VectorSearchConfig = Field(default_factory=VectorSearchConfig)
    hybrid_search: HybridSearchConfig = Field(default_factory=HybridSearchConfig)
    scheduled_jobs: ScheduledJobsConfig = Field(default_factory=ScheduledJobsConfig)


class LatticeConfig(BaseModel):
    """Lattice federation service configuration."""

    service_url: str = Field(
        default="http://localhost:1113",
        description="URL of the Lattice discovery service"
    )
    timeout: int = Field(
        default=30,
        description="HTTP request timeout in seconds"
    )


class ContextConfig(BaseModel):
    """
    Context window management configuration.

    Controls proactive token estimation and overflow remediation behavior.
    """
    topic_drift_window_size: int = Field(
        default=3,
        ge=2,
        description="Number of messages per sliding window for topic drift detection"
    )
    topic_drift_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Cosine similarity below this value indicates topic change"
    )
    overflow_fallback_prune_count: int = Field(
        default=5,
        ge=1,
        description="Number of oldest messages to prune when no topic drift boundary found"
    )
    tool_result_max_chars: int = Field(
        default=100_000,
        ge=1000,
        description="Max characters for a single tool result before truncation at storage time"
    )
    message_max_chars: int = Field(
        default=150_000,
        ge=10_000,
        description="Hard cap on any single message content before DB persistence"
    )


class ToolResultDisplayConfig(BaseModel):
    """
    Tool result persistence configuration.

    Controls whether tool use/result messages are persisted to the continuum
    for cross-turn visibility.
    """
    tombstone_mode: bool = Field(
        default=False,
        description="When True, tool results are NOT persisted to conversation history (tombstone = discard)"
    )


class PeanutGalleryConfig(BaseModel):
    """
    Peanut Gallery metacognitive observer configuration.

    Controls the async observer that monitors conversation from above, providing:
    - Compaction: Collapsing confusing, low-information sequences
    - Concern detection: Identifying unhealthy loops or emotional escalation
    - Coaching: Suggesting actions like forage_tool calls

    Runs every N turns as fire-and-forget background processing.
    """
    enabled: bool = Field(
        default=True,
        description="Whether the peanut gallery observer is enabled"
    )
    trigger_interval: int = Field(
        default=10,
        ge=1,
        description="Run observer evaluation every N turns"
    )
    message_window_pairs: int = Field(
        default=10,
        ge=3,
        description="Number of recent user/assistant pairs to show the observer (filters out tool messages)"
    )
    max_tokens: int = Field(
        default=500,
        ge=100,
        description="Maximum tokens for observer model response"
    )
    prerunner_max_tokens: int = Field(
        default=100,
        ge=50,
        description="Maximum tokens for prerunner (seed selection) response"
    )
    seed_memory_count: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Number of seed memories to provide to prerunner for relevance selection"
    )
    guidance_ttl_turns: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of turns guidance messages remain visible in HUD before expiring"
    )


class SidebarDispatcherConfig(BaseModel):
    """Sidebar agent dispatcher configuration."""
    enabled: bool = Field(
        default=True,
        description="Enable the sidebar dispatcher polling loop",
    )
    poll_interval_minutes: int = Field(
        default=1,
        description="Minutes between dispatcher poll cycles",
    )
    max_concurrent_agents: int = Field(
        default=3,
        ge=1,
        description="Maximum sidebar agent threads running simultaneously",
    )


class ImapTriggerConfig(BaseModel):
    """IMAP email trigger configuration for sidebar agents."""
    enabled: bool = Field(
        default=True,
        description="Enable IMAP polling for sidebar email agents",
    )
    watched_senders: List[str] = Field(
        default=["hello@rocketcitywindowcleaning.com"],
        description="Email addresses to monitor (e.g. contactform@example.com)",
    )
    max_age_hours: int = Field(
        default=24,
        description="Ignore emails older than this many hours. Prevents processing the entire inbox on first boot.",
    )

