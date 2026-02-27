"""
LT_Memory Module - Long-term memory system for MIRA.

Factory-based initialization with explicit dependency management.
"""
import logging

from config.config import LTMemoryConfig
from lt_memory.factory import LTMemoryFactory, get_lt_memory_factory
from lt_memory.db_access import LTMemoryDB
from lt_memory.vector_ops import VectorOps
from lt_memory.linking import LinkingService
from lt_memory.refinement import RefinementService
from lt_memory.proactive import ProactiveService
from lt_memory.models import (
    Memory,
    ExtractedMemory,
    MemoryLink,
    Entity,
    ProcessingChunk,
    ExtractionBatch,
    PostProcessingBatch,
    ConsolidationCluster,
    # Type aliases and TypedDicts
    RelationshipType,
    BatchStatus,
    BatchKind,
    MemoryLinkEntry,
    EntityLinkEntry,
    AnnotationEntry,
    LinkMetadata,
    TraversalResult,
    ClassificationPayload,
    ClassificationResult,
    ClassificationPair,
    EntityPairRow,
    GCStats,
    UserMemorySettings,
    MemoryPageResult,
    NamedEntity,
    MemoryContext,
    MemoryContextSnapshot,
    ChunkMetadata,
    MemoryDict,
    ConsolidationPayload,
)

logger = logging.getLogger(__name__)

__all__ = [
    # Factory
    'LTMemoryFactory',
    'get_lt_memory_factory',

    # Classes (for type hints)
    'LTMemoryDB',
    'VectorOps',
    'LinkingService',
    'RefinementService',
    'ProactiveService',
    'LTMemoryConfig',

    # Models
    'Memory',
    'ExtractedMemory',
    'MemoryLink',
    'Entity',
    'ProcessingChunk',
    'ExtractionBatch',
    'PostProcessingBatch',
    'ConsolidationCluster',
]
