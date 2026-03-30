"""
Peanut Gallery metacognitive observer model.

Two-stage LLM pipeline for conversation observation:
1. Prerunner (fast): Selects relevant seed memories from candidates
2. Observer (Sonnet 4.5): Evaluates conversation and decides action

Actions: noop, compaction, concern, coaching
"""
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Optional
from uuid import UUID

from cns.core.message import Message, preprocess_content_blocks
from clients.llm_provider import LLMProvider
from config.config import PeanutGalleryConfig
from lt_memory.linking import LinkingService
from lt_memory.models import MemoryDict, TraversalResult

logger = logging.getLogger(__name__)


@dataclass
class PeanutGalleryResult:
    """Result from the Peanut Gallery observer evaluation."""
    action_type: Literal["noop", "compaction", "concern", "coaching"]
    # Compaction fields
    range_start: Optional[str] = None
    range_end: Optional[str] = None
    synopsis: Optional[str] = None
    # Concern/coaching fields
    guidance: Optional[str] = None


class PeanutGalleryModel:
    """
    Two-stage LLM model for metacognitive conversation observation.

    Stage 1 (Prerunner): Fast model selects relevant memories from seed pool
    Stage 2 (Observer): Sonnet 4.5 evaluates conversation with memory context

    The observer can output:
    - noop: No action needed
    - compaction: Collapse confusing message range into synopsis
    - concern: Alert about unhealthy patterns
    - coaching: Suggest beneficial actions
    """

    def __init__(
        self,
        config: PeanutGalleryConfig,
        llm_provider: LLMProvider,
        linking_service: LinkingService
    ):
        """
        Initialize Peanut Gallery model.

        Args:
            config: PeanutGallery configuration
            llm_provider: LLM provider for model calls
            linking_service: For traversing memory links
        """
        self.config = config
        self.llm_provider = llm_provider
        self.linking = linking_service

        # Load prompt templates
        prompts_dir = Path("config/prompts")

        self._prerunner_prompt = self._load_prompt(prompts_dir / "peanutgallery_prerunner.txt")
        self._system_prompt = self._load_prompt(prompts_dir / "peanutgallery_system.txt")
        self._user_template = self._load_prompt(prompts_dir / "peanutgallery_user.txt")

        logger.info("PeanutGalleryModel initialized")

    def _load_prompt(self, path: Path) -> str:
        """Load prompt template from file."""
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        return path.read_text()

    def evaluate(
        self,
        messages: List[Message],
        seed_memories: list[MemoryDict]
    ) -> PeanutGalleryResult:
        """
        Evaluate conversation with two-stage LLM pipeline.

        Args:
            messages: Recent messages from conversation cache
            seed_memories: Candidate memories for context (from ProactiveService)

        Returns:
            PeanutGalleryResult with action_type and relevant fields
        """
        # Stage 1: Prerunner selects relevant seed memories
        selected_indices = self._run_prerunner(messages, seed_memories)

        # Build memory context from selected seeds + link traversal
        memory_context = self._build_memory_context(seed_memories, selected_indices)

        # Stage 2: Observer evaluates conversation
        return self._run_observer(messages, memory_context)

    def _run_prerunner(
        self,
        messages: List[Message],
        seed_memories: list[MemoryDict]
    ) -> List[int]:
        """
        Run prerunner to select relevant seed memories.

        Args:
            messages: Recent conversation messages
            seed_memories: Indexed candidate memories

        Returns:
            List of selected indices (0-based)
        """
        if not seed_memories:
            return []

        # Format conversation for prerunner
        formatted_conversation = self._format_conversation_brief(messages)

        # Format indexed memories
        indexed_memories = self._format_indexed_memories(seed_memories)

        # Build prerunner prompt
        prerunner_prompt = self._prerunner_prompt.replace(
            "{formatted_conversation}", formatted_conversation
        ).replace(
            "{indexed_memories}", indexed_memories
        )

        # Call prerunner (fast model, low tokens)
        response = self.llm_provider.generate_response(
            messages=[{"role": "user", "content": prerunner_prompt}],
            stream=False,
            internal_llm='analysis',
            max_tokens=self.config.prerunner_max_tokens
        )

        response_text = self.llm_provider.extract_text_content(response).strip()

        # Parse selected indices
        return self._parse_prerunner_response(response_text, len(seed_memories))

    def _parse_prerunner_response(
        self,
        response_text: str,
        max_index: int
    ) -> List[int]:
        """
        Parse prerunner response to extract selected indices.

        Expected format: <selected_seeds>0, 3, 7</selected_seeds>
        Or: <selected_seeds>none</selected_seeds>
        """
        match = re.search(
            r'<selected_seeds>(.*?)</selected_seeds>',
            response_text,
            re.DOTALL | re.IGNORECASE
        )

        if not match:
            logger.debug("No <selected_seeds> tag in prerunner response")
            return []

        content = match.group(1).strip().lower()

        if content == "none":
            return []

        # Parse comma-separated indices
        indices = []
        for part in content.split(','):
            part = part.strip()
            if part.isdigit():
                idx = int(part)
                if 0 <= idx < max_index:
                    indices.append(idx)

        logger.debug(f"Prerunner selected {len(indices)} seed memories: {indices}")
        return indices

    def _build_memory_context(
        self,
        seed_memories: list[MemoryDict],
        selected_indices: List[int]
    ) -> str:
        """
        Build memory context from selected seeds plus link traversal.

        For each selected seed, traverses up to depth=2 to gather related
        memories for richer context.
        """
        if not selected_indices:
            return "<memory_context>No relevant memories selected.</memory_context>"

        parts = ["<memory_context>"]
        seen_ids = set()

        for idx in selected_indices:
            if idx >= len(seed_memories):
                continue

            memory = seed_memories[idx]
            memory_id = memory['id']
            memory_text = memory['text']

            if not memory_id or memory_id in seen_ids:
                continue

            seen_ids.add(memory_id)

            # Add seed memory
            short_id = str(memory_id)[:8]
            parts.append(f"<seed id=\"{short_id}\">{memory_text}</seed>")

            # Traverse links for this memory
            try:
                memory_uuid = UUID(str(memory_id))
                related: list[TraversalResult] = self.linking.traverse_related(memory_uuid, depth=2)

                for rel in related[:5]:  # Limit related per seed
                    rel_memory = rel['memory']
                    if rel_memory.id not in seen_ids:
                        seen_ids.add(rel_memory.id)
                        rel_id = str(rel_memory.id)[:8]
                        link_type = rel['link_type'] or 'related'
                        parts.append(
                            f"<linked id=\"{rel_id}\" via=\"{link_type}\">"
                            f"{rel_memory.text}</linked>"
                        )
            except Exception as e:
                logger.debug(f"Link traversal failed for {memory_id}: {e}")

        parts.append("</memory_context>")
        return "\n".join(parts)

    def _run_observer(
        self,
        messages: List[Message],
        memory_context: str
    ) -> PeanutGalleryResult:
        """
        Run observer to evaluate conversation and decide action.

        Args:
            messages: Recent conversation messages
            memory_context: Built from selected seeds + links

        Returns:
            PeanutGalleryResult with action and details
        """
        # Extract message pairs for observer
        pairs = self._extract_message_pairs(messages)
        recent_pairs = pairs[-self.config.message_window_pairs:]

        if len(recent_pairs) < 3:
            logger.debug("Not enough message pairs for observer evaluation")
            return PeanutGalleryResult(action_type="noop")

        # Format messages with IDs
        formatted_messages = self._format_with_ids(recent_pairs)

        # Build user prompt
        user_prompt = self._user_template.replace(
            "{formatted_messages}", formatted_messages
        ).replace(
            "{memory_context}", memory_context
        )

        # Call observer (Sonnet 4.5)
        response = self.llm_provider.generate_response(
            messages=[{"role": "user", "content": user_prompt}],
            stream=False,
            internal_llm='tidyup',
            system_override=self._system_prompt
        )

        response_text = self.llm_provider.extract_text_content(response).strip()

        if not response_text:
            logger.debug("Observer returned empty response")
            return PeanutGalleryResult(action_type="noop")

        return self._parse_observer_response(response_text)

    def _parse_observer_response(self, response_text: str) -> PeanutGalleryResult:
        """
        Parse observer response into PeanutGalleryResult.

        Expected formats:
        - <mira:noop/>
        - <mira:peanutgallery type="compaction">...</mira:peanutgallery>
        - <mira:peanutgallery type="concern">...</mira:peanutgallery>
        - <mira:peanutgallery type="coaching">...</mira:peanutgallery>
        """
        # Check for noop
        if re.search(r'<mira:noop\s*/>', response_text, re.IGNORECASE):
            logger.debug("Observer: noop")
            return PeanutGalleryResult(action_type="noop")

        # Check for peanutgallery tag with type
        pg_match = re.search(
            r'<mira:peanutgallery\s+type="(\w+)">(.*?)</mira:peanutgallery>',
            response_text,
            re.DOTALL | re.IGNORECASE
        )

        if not pg_match:
            logger.debug("Malformed observer response, treating as noop")
            return PeanutGalleryResult(action_type="noop")

        action_type = pg_match.group(1).lower()
        content = pg_match.group(2)

        if action_type == "compaction":
            return self._parse_compaction(content)
        elif action_type in ("concern", "coaching"):
            return self._parse_guidance(action_type, content)
        else:
            logger.warning(f"Unknown action type: {action_type}")
            return PeanutGalleryResult(action_type="noop")

    def _parse_compaction(self, content: str) -> PeanutGalleryResult:
        """Parse compaction action from content."""
        range_match = re.search(
            r'<range\s+start="([^"]+)"\s+end="([^"]+)"\s*/>',
            content
        )
        synopsis_match = re.search(
            r'<synopsis>(.*?)</synopsis>',
            content,
            re.DOTALL
        )

        if not range_match or not synopsis_match:
            logger.debug("Malformed compaction response")
            return PeanutGalleryResult(action_type="noop")

        return PeanutGalleryResult(
            action_type="compaction",
            range_start=range_match.group(1),
            range_end=range_match.group(2),
            synopsis=synopsis_match.group(1).strip()
        )

    def _parse_guidance(
        self,
        guidance_type: Literal["concern", "coaching"],
        content: str
    ) -> PeanutGalleryResult:
        """Parse concern or coaching guidance from content."""
        guidance_match = re.search(
            r'<guidance>(.*?)</guidance>',
            content,
            re.DOTALL
        )

        if not guidance_match:
            logger.debug(f"Malformed {guidance_type} response")
            return PeanutGalleryResult(action_type="noop")

        return PeanutGalleryResult(
            action_type=guidance_type,
            guidance=guidance_match.group(1).strip()
        )

    def _extract_message_pairs(self, messages: List[Message]) -> List[Message]:
        """
        Extract user/assistant message pairs, filtering out tool messages.

        Tool call messages (role='tool') and messages with tool_use metadata
        are filtered out to focus on the actual conversation flow.
        """
        pairs = []
        for msg in messages:
            # Skip tool messages
            if msg.role == 'tool':
                continue

            # Skip segment boundary markers
            metadata = msg.metadata or {}
            if metadata.get('is_segment_boundary'):
                continue

            # Skip messages that are just tool call wrappers
            if metadata.get('has_tool_calls') and not msg.content:
                continue

            # Include user and assistant messages with actual content
            if msg.role in ('user', 'assistant') and msg.content:
                pairs.append(msg)

        return pairs

    def _format_with_ids(self, messages: List[Message]) -> str:
        """
        Format messages with 8-char IDs for observer evaluation.

        Format: [ID:xxxxxxxx] role: content
        """
        lines = []
        for msg in messages:
            msg_id = str(msg.id)[:8]

            # Resolve multimodal content to text, then truncate
            content = msg.content
            if isinstance(content, list):
                preprocessed = preprocess_content_blocks(content)
                content = " ".join(preprocessed.text_parts)
                if preprocessed.image_count > 0:
                    content = f"[{preprocessed.image_count} image(s) shared] {content}".strip()
            if isinstance(content, str) and len(content) > 500:
                content = content[:500] + "... [truncated]"

            lines.append(f"[ID:{msg_id}] {msg.role}: {content}")

        return "\n".join(lines)

    def _format_conversation_brief(self, messages: List[Message]) -> str:
        """Format conversation briefly for prerunner (just role + first 100 chars)."""
        pairs = self._extract_message_pairs(messages)
        recent = pairs[-6:]  # Last 3 pairs for prerunner context

        lines = []
        for msg in recent:
            content = msg.content
            if isinstance(content, list):
                preprocessed = preprocess_content_blocks(content)
                content = " ".join(preprocessed.text_parts)
                if preprocessed.image_count > 0:
                    content = f"[{preprocessed.image_count} image(s) shared] {content}".strip()
            if isinstance(content, str) and len(content) > 100:
                content = content[:100] + "..."
            lines.append(f"{msg.role}: {content}")

        return "\n".join(lines)

    def _format_indexed_memories(self, memories: list[MemoryDict]) -> str:
        """Format memories with indices for prerunner selection."""
        lines = []
        for i, memory in enumerate(memories):
            text = memory['text'][:150]
            lines.append(f"[{i}] {text}")
        return "\n".join(lines)
