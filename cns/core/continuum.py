"""
Continuum aggregate root for CNS.

Mutable aggregate that encapsulates business logic and state transitions.
ContinuumState is frozen, but the aggregate itself maintains a mutable
message cache that is appended to during processing and replaced on
session reload.
"""
from __future__ import annotations

import logging
from uuid import UUID, uuid4

from .message import Message, MessageMetadata, ContentBlock
from .state import ContinuumState, ContinuumStateDict
from .events import ContinuumEvent

logger = logging.getLogger(__name__)


class Continuum:
    """
    Continuum aggregate root.

    Manages continuum state and message cache. ContinuumState is frozen,
    but the message cache is mutable (appended during turns, replaced on reload).
    """

    def __init__(self, state: ContinuumState):
        """Initialize continuum with state."""
        self._state = state
        self._message_cache: list[Message] = []  # Hot cache of recent messages

    @classmethod
    def create_new(cls, user_id: str) -> Continuum:
        """Create a new continuum for user."""
        state = ContinuumState(
            id=uuid4(),
            user_id=user_id
        )
        return cls(state)
    
    @property
    def id(self) -> UUID:
        """Get continuum ID."""
        return self._state.id

    @property
    def user_id(self) -> str:
        """Get user ID."""
        return self._state.user_id

    @property
    def messages(self) -> list[Message]:
        """Get cached messages - must be initialized through ContinuumPool."""
        return self._message_cache

    def apply_cache(self, messages: list[Message]) -> None:
        """
        Apply an externally managed cache update.
        
        Used by segment cache loader to update the cache after operations
        like segment reconstruction and message loading.
        
        Args:
            messages: New message cache to apply
        """
        self._message_cache = messages
    
    def add_user_message(self, content: str | list[ContentBlock]) -> tuple[Message, list[ContinuumEvent]]:
        """
        Add user message to continuum.

        Returns:
            Tuple of (created Message, list of domain events)
        """
        # Create message with original content for processing
        message = Message(content=content, role="user")

        # Add to cache only - persistence will be handled by orchestrator
        self._message_cache.append(message)

        return message, []
    
    def add_assistant_message(self, content: str, metadata: MessageMetadata | None = None) -> tuple[Message, list[ContinuumEvent]]:
        """
        Add assistant message to continuum.

        Returns:
            Tuple of (created Message, list of domain events)
        """
        # Validate content is not blank
        if not content or not content.strip():
            raise ValueError("Assistant message content cannot be blank or empty")

        # Create message
        message = Message(content=content, role="assistant", metadata=metadata or {})

        # Add to cache only - persistence will be handled by orchestrator
        self._message_cache.append(message)

        return message, []
    
    def add_tool_message(self, content: str, tool_call_id: str) -> list[ContinuumEvent]:
        """
        Add tool result message to continuum.

        Returns:
            List of domain events (empty for tool messages)
        """
        # Create message
        message = Message(
            content=content,
            role="tool",
            metadata={"tool_call_id": tool_call_id}
        )

        # Add to cache only - persistence will be handled by orchestrator
        self._message_cache.append(message)

        # Tool messages don't generate events by themselves
        return []

    def add_tool_history(self, messages: list[Message]) -> None:
        """
        Insert tool history messages into the cache.

        Called after turn completion to persist tool use/result pairs
        so subsequent turns can see what tools returned.
        """
        self._message_cache.extend(messages)

    def get_messages_for_api(self) -> list[dict[str, object]]:
        """Get messages formatted for LLM API with proper prefixes and cache control.

        Tool messages (role="tool") are buffered and flushed as a single
        role="user" message with tool_result content blocks — the format
        the Anthropic API expects for multi-turn tool use history.
        """
        from cns.services.segment_helpers import format_segment_for_display, format_precis_for_display
        from utils.timezone_utils import convert_from_utc
        from utils.user_context import get_user_preferences

        # Get user timezone for timestamp injection
        user_tz = get_user_preferences().timezone

        formatted_messages: list[dict[str, object]] = []
        pending_tool_results: list[dict[str, object]] = []

        def _flush_tool_results() -> None:
            """Flush buffered tool results as a single user message with tool_result blocks."""
            if not pending_tool_results:
                return
            formatted_messages.append({
                "role": "user",
                "content": list(pending_tool_results)
            })
            pending_tool_results.clear()

        for message in self.messages:
            # --- Tool result messages: buffer and continue ---
            if message.role == "tool":
                pending_tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": message.metadata.get("tool_call_id"),
                    "content": message.content
                })
                continue

            # Flush any pending tool results before a non-tool message
            _flush_tool_results()

            # Format content based on message type
            content = message.content

            # Collapsed segments → synthetic continuum_tool call/result pair.
            # Tool result framing gives summaries higher attention weight than
            # plain assistant messages — the model treats them as retrieved data.
            if (message.metadata.get('is_segment_boundary') and
                message.metadata.get('status') == 'collapsed'):
                display_mode = message.metadata.get('display_mode', 'extended')
                if display_mode == 'precis':
                    summary_content = format_precis_for_display(message)
                elif display_mode == 'extended':
                    summary_content = format_segment_for_display(message)
                else:
                    raise ValueError(f"Unknown display_mode '{display_mode}' on segment {message.metadata.get('segment_id')}")
                tool_use_id = f"toolu_seg_{message.metadata['segment_id'][:22]}"

                formatted_messages.append({
                    "role": "assistant",
                    "content": [{
                        "type": "tool_use",
                        "id": tool_use_id,
                        "name": "continuum_tool",
                        "input": {"operation": "search", "query": message.metadata['display_title']}
                    }]
                })
                formatted_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": summary_content
                    }]
                })
                continue

            # Inject ephemeral timestamps for user/assistant messages (not persisted).
            # Skip timestamp injection for tool-call assistant messages — they're
            # structural (contain tool_use blocks), not conversational.
            elif (message.role in ("user", "assistant") and
                  not message.metadata.get('is_segment_boundary') and
                  not message.metadata.get('system_notification') and
                  not message.metadata.get('has_tool_calls')):
                local_dt = convert_from_utc(message.created_at, user_tz)
                timestamp = local_dt.strftime("%-I:%M%p").lower()
                if isinstance(content, str):
                    content = f"[{timestamp}] {content}"
                elif isinstance(content, list):
                    # Shallow copy to avoid mutating the frozen Message's content
                    content = [block.copy() for block in content]
                    for block in content:
                        if block.get("type") == "text":
                            block["text"] = f"[{timestamp}] {block['text']}"
                            break

            if message.role == "assistant" and message.metadata.get("has_tool_calls", False):
                # Assistant message with tool calls — content is already structured
                # blocks (tool_use blocks from _build_tool_history_messages)
                if isinstance(content, str):
                    content = [{"type": "text", "text": content}]
                # Prepend thinking blocks if preserved from response
                thinking_blocks = message.metadata.get("thinking_blocks", [])
                if thinking_blocks:
                    content = list(thinking_blocks) + list(content)
                formatted_messages.append({
                    "role": "assistant",
                    "content": content
                })
            elif message.role == "assistant":
                # Always use structured blocks so block format stays identical
                # when cache_control moves to a newer message next turn
                if isinstance(content, str):
                    content = [{"type": "text", "text": content}]
                # Prepend thinking blocks if preserved from response
                thinking_blocks = message.metadata.get("thinking_blocks", [])
                if thinking_blocks:
                    content = list(thinking_blocks) + list(content)
                formatted_messages.append({
                    "role": "assistant",
                    "content": content
                })
            elif message.role == "user" and isinstance(message.content, list):
                # User message with content blocks (multimodal)
                formatted_messages.append({
                    "role": "user",
                    "content": message.content  # Keep original for multimodal
                })
            else:
                # Standard text message (user, system)
                formatted_messages.append({
                    "role": message.role,
                    "content": content
                })

        # Flush any trailing tool results
        _flush_tool_results()

        # Apply cache_control to last assistant message for conversation history caching.
        # All assistant messages are already structured blocks (normalized above),
        # so we just annotate the last one. Anthropic ignores cache markers on content
        # below the minimum token threshold, so always mark and let the API decide.
        for i in range(len(formatted_messages) - 1, -1, -1):
            if formatted_messages[i]["role"] == "assistant":
                content = formatted_messages[i]["content"]
                if isinstance(content, list) and len(content) > 0:
                    content[-1]["cache_control"] = {"type": "ephemeral", "ttl": "1h"}
                break

        return formatted_messages
    
    def to_dict(self) -> ContinuumStateDict:
        """Convert continuum to dictionary for persistence."""
        return self._state.to_dict()

    @classmethod
    def from_dict(cls, data: ContinuumStateDict) -> Continuum:
        """Create continuum from dictionary."""
        state = ContinuumState.from_dict(data)
        return cls(state)