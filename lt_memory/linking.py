"""
Relationship discovery and link management for LT_Memory system.

Handles finding semantically related memories, classifying relationship types,
and creating bidirectional links in the memory graph. Supports both synchronous
link creation and batch classification payload building.
"""
import json
import logging
from pathlib import Path
from typing import List, Optional, Union
from uuid import UUID

from lt_memory.models import Memory, MemoryLink, ClassificationPayload, ClassificationResult, TraversalResult, VALID_RELATIONSHIP_TYPES
from config.config import LinkingConfig
from lt_memory.vector_ops import VectorOps
from lt_memory.db_access import LTMemoryDB
from clients.llm_provider import LLMProvider
from utils.timezone_utils import utc_now, format_utc_iso

logger = logging.getLogger(__name__)


class LinkingService:
    """
    Service for discovering and managing memory relationships.

    Provides:
    - Similarity-based candidate discovery
    - Relationship classification (sync or batch payload building)
    - Bidirectional link creation and management
    - Link traversal for graph navigation
    """

    def __init__(
        self,
        config: LinkingConfig,
        vector_ops: VectorOps,
        db: LTMemoryDB,
        llm_provider: Optional[LLMProvider] = None
    ):
        """
        Initialize linking service.

        Args:
            config: Linking configuration
            vector_ops: Vector operations for similarity search
            db: Database access layer
            llm_provider: LLM provider for sync classification (optional)
        """
        self.config = config
        self.vector_ops = vector_ops
        self.db = db
        self.llm_provider = llm_provider
        self._load_prompts()

    def _load_prompts(self) -> None:
        """
        Load relationship classification prompt.

        Raises:
            FileNotFoundError: If prompt file not found (prompts are required configuration)
        """
        prompt_path = Path("config/prompts/memory_relationship_classification.txt")

        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Required prompt file not found: {prompt_path}. "
                f"Prompts are system configuration, not optional features."
            )

        with open(prompt_path, 'r', encoding='utf-8') as f:
            self.relationship_system_prompt = f.read().strip()

        logger.info("Loaded relationship classification prompt")

    def find_similar_candidates(
        self,
        memory_id: UUID
    ) -> List[Memory]:
        """
        Find candidate memories for relationship classification.

        Uses two discovery axes:
        1. Vector similarity — finds memories with similar embedding content
        2. Entity co-occurrence — finds memories sharing entities (people,
           places, orgs) regardless of embedding distance

        The union of both axes feeds the classifier, which decides whether
        each candidate pair has a meaningful relationship.

        Args:
            memory_id: Source memory UUID

        Returns:
            List of candidate Memory objects (excludes source memory)
        """
        # Axis 1: Vector similarity (existing behavior)
        vector_candidates = self.vector_ops.find_similar_to_memory(
            memory_id=memory_id,
            limit=self.config.max_candidates_per_memory,
            similarity_threshold=self.config.similarity_threshold_for_linking,
            min_importance=0.001  # Filter cold storage (0.0) memories
        )

        # Axis 2: Entity co-occurrence
        entity_candidates = self._find_entity_candidates(memory_id)

        # Union and deduplicate
        seen_ids = set()
        combined = []
        for mem in vector_candidates + entity_candidates:
            if mem.id not in seen_ids and mem.id != memory_id:
                seen_ids.add(mem.id)
                combined.append(mem)

        logger.debug(
            f"Found {len(combined)} candidates for memory {memory_id} "
            f"(vector={len(vector_candidates)}, entity={len(entity_candidates)}, "
            f"unique={len(combined)})"
        )

        return combined

    def _find_entity_candidates(
        self,
        memory_id: UUID
    ) -> List[Memory]:
        """
        Find memories that share entities with the source memory.

        For each entity linked to the source memory, retrieves other memories
        also linked to that entity. This catches cross-domain connections where
        memories share people/places/orgs but have distant embeddings (e.g.,
        "Annika is vegetarian" + "planning birthday dinner for Annika").

        Args:
            memory_id: Source memory UUID

        Returns:
            List of candidate Memory objects (excludes source, cold storage)
        """
        source_memory = self.db.get_memory(memory_id)
        if not source_memory or not source_memory.entity_links:
            return []

        seen_ids = {memory_id}  # Exclude source
        candidates = []

        for entity_link in source_memory.entity_links:
            entity_id = entity_link.get("uuid")
            if not entity_id:
                continue

            try:
                entity_uuid = UUID(entity_id)
            except ValueError:
                logger.warning(f"Malformed entity UUID in entity_links: {entity_id}")
                continue

            co_occurring = self.db.get_memories_for_entity(entity_uuid)

            for mem in co_occurring:
                if mem.id in seen_ids:
                    continue
                if mem.importance_score is not None and mem.importance_score <= 0.0:
                    continue  # Skip cold storage
                seen_ids.add(mem.id)
                candidates.append(mem)

        return candidates

    def build_classification_payload(
        self,
        source_memory: Memory,
        target_memory: Memory,
        bond: str = ""
    ) -> ClassificationPayload:
        """
        Build relationship classification request payload for batch API.

        Creates the prompt and parameters needed for LLM classification
        without making the actual call.

        Args:
            source_memory: Source memory
            target_memory: Target memory for comparison
            bond: Extraction-time bond descriptor (3-word hint from extraction LLM)

        Returns:
            Dictionary with prompt and classification parameters
        """
        # Build user prompt
        user_prompt = self._build_relationship_prompt(source_memory, target_memory, bond=bond)

        return {
            "source_id": str(source_memory.id),
            "target_id": str(target_memory.id),
            "system_prompt": self.relationship_system_prompt,
            "user_prompt": user_prompt
        }

    def _format_temporal_fields(self, memory: Memory) -> str:
        """
        Format temporal fields for prompt display.

        Args:
            memory: Memory object

        Returns:
            Formatted temporal info string
        """
        parts = []

        if memory.happens_at:
            parts.append(f"happens_at: {format_utc_iso(memory.happens_at)}")

        if memory.expires_at:
            parts.append(f"expires_at: {format_utc_iso(memory.expires_at)}")

        return " | ".join(parts) if parts else "no temporal constraints"

    def _build_relationship_prompt(
        self,
        source_memory: Memory,
        target_memory: Memory,
        bond: str = ""
    ) -> str:
        """
        Build user prompt for relationship classification.

        Args:
            source_memory: Source memory
            target_memory: Target memory
            bond: Extraction-time bond descriptor (optional context hint)

        Returns:
            Formatted prompt text
        """
        source_temporal = self._format_temporal_fields(source_memory)
        target_temporal = self._format_temporal_fields(target_memory)

        extraction_context = ""
        if bond:
            extraction_context = f"\nExtraction context: \"{bond}\"\n"

        prompt = f"""Classify the relationship between these memories:

NEW MEMORY:
Text: "{source_memory.text}"
Temporal: {source_temporal}
Importance: {source_memory.importance_score:.3f}

EXISTING MEMORY:
Text: "{target_memory.text}"
Temporal: {target_temporal}
Importance: {target_memory.importance_score:.3f}
{extraction_context}
Would knowing one of these memories change how you'd act on the other? If so, classify the connection.

Respond with JSON:
{{
    "relationship_type": "supports|conflicts|supersedes|refines|precedes|contextualizes|null",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation"
}}"""

        return prompt

    # DEAD CODE — no active callers (verified 2026-02-26). Candidate for removal.
    def _parse_classification_response(
        self,
        response_text: str
    ) -> Optional[ClassificationResult]:
        """
        Parse relationship classification response from LLM.

        Args:
            response_text: LLM response (JSON format)

        Returns:
            Parsed classification dict or None if invalid
        """
        try:
            classification = json.loads(response_text)

            # Validate required fields
            if not isinstance(classification, dict):
                logger.warning("Classification response is not a dict")
                return None

            relationship_type = classification.get("relationship_type")
            if not relationship_type:
                logger.warning("Classification missing relationship_type")
                return None

            # Validate relationship type
            if relationship_type not in VALID_RELATIONSHIP_TYPES:
                logger.warning(f"Invalid relationship type: {relationship_type}")
                return None

            return classification

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse classification response: {e}")
            return None

    # DEAD CODE — no active callers (verified 2026-02-26). Candidate for removal.
    def classify_relationship_sync(
        self,
        source_memory: Memory,
        target_memory: Memory
    ) -> Optional[MemoryLink]:
        """
        Synchronously classify relationship and create link.

        Makes immediate LLM call for classification. Use sparingly -
        prefer batch classification for cost efficiency.

        Args:
            source_memory: Source memory
            target_memory: Target memory

        Returns:
            MemoryLink object or None if confidence below threshold

        Raises:
            RuntimeError: If LLM provider not configured or LLM call fails
        """
        if not self.llm_provider:
            raise RuntimeError(
                "LLM provider required for synchronous classification"
            )

        # Build prompt
        user_prompt = self._build_relationship_prompt(source_memory, target_memory)

        # Call LLM using relationship internal LLM config
        response = self.llm_provider.generate_response(
            messages=[
                {"role": "system", "content": self.relationship_system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            internal_llm='relationship',
            allow_negative=True,  # System task - complete even if user balance negative
        )

        response_text = self.llm_provider.extract_text_content(response)

        # Parse classification
        classification = self._parse_classification_response(response_text)

        if not classification:
            return None

        # Check confidence threshold
        confidence = classification.get("confidence", 0.0)
        if confidence < self.config.link_confidence_threshold:
            logger.debug(
                f"Link confidence {confidence:.2f} below threshold "
                f"{self.config.link_confidence_threshold}"
            )
            return None

        # Create MemoryLink
        link = MemoryLink(
            source_id=source_memory.id,
            target_id=target_memory.id,
            link_type=classification["relationship_type"],
            confidence=confidence,
            reasoning=classification.get("reasoning", ""),
            created_at=utc_now()
        )

        return link

    def create_bidirectional_link(
        self,
        source_id: UUID,
        target_id: UUID,
        link_type: str,
        confidence: float,
        reasoning: str,
        extraction_bond: str = ""
    ) -> bool:
        """
        Create single bidirectional link between memories.

        Convenience method for creating one link. For batch operations,
        use create_bidirectional_links() instead.

        Args:
            source_id: Source memory UUID
            target_id: Target memory UUID
            link_type: Relationship type (conflicts, supports, supersedes, related)
            confidence: Link confidence (0.0-1.0)
            reasoning: Explanation of relationship
            extraction_bond: 3-word bond from extraction LLM (preserved as-is)

        Returns:
            True if link created successfully

        Raises:
            Exception: If database operation fails
        """
        link = MemoryLink(
            source_id=source_id,
            target_id=target_id,
            link_type=link_type,
            confidence=confidence,
            reasoning=reasoning,
            extraction_bond=extraction_bond,
            created_at=utc_now()
        )

        self.db.create_links([link])
        logger.info(f"Created {link_type} link: {source_id} <-> {target_id}")
        return True

    def create_bidirectional_links(
        self,
        links: Union[MemoryLink, List[MemoryLink]]
    ) -> None:
        """
        Create bidirectional link(s) between memories.

        Updates both source and target memory link arrays.

        Args:
            links: Single MemoryLink or list of MemoryLink objects
        """
        # Normalize to list
        if isinstance(links, MemoryLink):
            links = [links]

        if not links:
            return

        self.db.create_links(links)

        if len(links) == 1:
            link = links[0]
            logger.info(
                f"Created bidirectional {link.link_type} link: "
                f"{link.source_id} <-> {link.target_id}"
            )
        else:
            logger.info(f"Created {len(links)} bidirectional links")

    def traverse_related(
        self,
        memory_id: UUID,
        depth: Optional[int] = None
    ) -> List[TraversalResult]:
        """
        Traverse memory graph from starting memory with link metadata.

        Follows outbound links up to specified depth, collecting related memories
        with their link information (type, confidence, reasoning) and hierarchical
        position preserved for display.

        Args:
            memory_id: Starting memory UUID
            depth: Maximum traversal depth (uses config default if None)

        Returns:
            List of dicts with Memory object and link metadata:
            [
                {
                    "memory": Memory,
                    "link_type": str,
                    "confidence": float,
                    "reasoning": str,
                    "depth": int,
                    "linked_from_id": UUID
                },
                ...
            ]
        """
        if depth is None:
            depth = self.config.max_link_traversal_depth

        if depth < 1:
            return []

        visited_ids = {memory_id}
        current_level = [(memory_id, None, 0)]  # (uuid, link_metadata, depth)
        all_related = []

        for current_depth in range(1, depth + 1):
            if not current_level:
                break

            # Get UUIDs for this level
            level_uuids = [item[0] for item in current_level]
            current_memories = self.db.get_memories_by_ids(level_uuids)

            # Heal-on-read: detect and remove dead links
            found_memory_ids = {m.id for m in current_memories}
            dead_links = [uuid for uuid in level_uuids if uuid not in found_memory_ids]

            if dead_links:
                removed_count = self.db.remove_dead_links(dead_links)
                if removed_count > 0:
                    logger.info(
                        f"Heal-on-read removed {removed_count} dead link references "
                        f"for {len(dead_links)} UUIDs during traversal"
                    )

            # Build memory lookup
            memory_lookup = {m.id: m for m in current_memories}

            # Process current level and extract next level
            next_level = []
            for uuid, link_meta, depth_level in current_level:
                memory = memory_lookup.get(uuid)
                if not memory:
                    continue

                # Add to results (skip starting memory)
                if uuid != memory_id:
                    all_related.append({
                        "memory": memory,
                        "link_type": link_meta.get("type") if link_meta else None,
                        "confidence": link_meta.get("confidence") if link_meta else None,
                        "reasoning": link_meta.get("reasoning") if link_meta else None,
                        "depth": depth_level,
                        "linked_from_id": link_meta.get("source_id") if link_meta else None
                    })

                # Extract outbound links for next level
                for link in memory.outbound_links:
                    target_uuid = UUID(link["uuid"])

                    if target_uuid not in visited_ids:
                        visited_ids.add(target_uuid)
                        next_level.append((
                            target_uuid,
                            {
                                "type": link.get("type"),
                                "confidence": link.get("confidence"),
                                "reasoning": link.get("reasoning"),
                                "source_id": uuid
                            },
                            current_depth
                        ))

            current_level = next_level

        return all_related

    def cleanup(self) -> None:
        """
        Clean up resources.

        No-op: Dependencies managed by factory lifecycle.
        Nulling references breaks in-flight scheduler jobs.
        """
        logger.debug("LinkingService cleanup completed (no-op)")
