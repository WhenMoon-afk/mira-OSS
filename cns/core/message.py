"""
Message value objects for CNS.

Immutable message representations that capture the essential business logic
without external dependencies. Timezone handling follows UTC-everywhere approach.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TypedDict
from uuid import UUID, uuid4
from utils.timezone_utils import utc_now


class TextBlock(TypedDict, total=False):
    """Text content block in a multimodal message."""
    type: str  # "text"
    text: str
    cache_control: dict[str, str]


class ImageBlock(TypedDict, total=False):
    """Image content block in a multimodal message."""
    type: str  # "image"
    source: dict[str, object]


class DocumentBlock(TypedDict, total=False):
    """Document content block in a multimodal message."""
    type: str  # "document"
    source: dict[str, object]


class ContainerUploadBlock(TypedDict, total=False):
    """Container file upload content block."""
    type: str  # "container_upload"
    container_id: str
    file_id: str


ContentBlock = TextBlock | ImageBlock | DocumentBlock | ContainerUploadBlock


class MessageMetadata(TypedDict, total=False):
    """All known metadata keys on Message.metadata."""
    # Segment boundary fields
    is_segment_boundary: bool
    status: str  # "active" | "collapsed"
    segment_id: str
    segment_start_time: str
    segment_end_time: str
    display_title: str
    complexity_score: int
    tools_used: list[str]
    segment_embedding_value: list[float]
    has_segment_embedding: bool
    collapse_attempts: int
    extraction_attempts: int
    # Tool call fields
    has_tool_calls: bool
    tool_calls: list[dict[str, object]]
    tool_call_id: str
    # System notification fields
    system_notification: bool | str
    notification_type: str
    # LLM response fields
    emotion: str
    thinking: str
    model_error: bool
    model_error_reason: str
    # Embedding fields
    embedding_value: list[float]
    # Memory fields
    referenced_memories: list[str]
    surfaced_memories: list[str]
    pinned_memory_ids: list[str]
    # Compaction fields
    is_compaction_synopsis: bool
    compacted_count: int
    original_start_time: str
    original_end_time: str


@dataclass(frozen=True)
class Message:
    """
    Immutable message value object.
    
    Represents a single message in a continuum with proper timezone handling
    and immutable state management.
    """
    content: str | list[ContentBlock]
    role: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    metadata: MessageMetadata = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate message on creation."""
        if self.role not in ["user", "assistant", "tool"]:
            raise ValueError(f"Invalid role: {self.role}. Must be 'user', 'assistant', or 'tool'")
        
        # Check for empty content - handle both None and empty strings
        # Allow assistant messages with tool calls but no content
        if self.content is None or (isinstance(self.content, str) and self.content.strip() == ""):
            if not (self.role == "assistant" and self.metadata.get("has_tool_calls", False)):
                raise ValueError(f"Message content cannot be empty for {self.role} messages")
    
    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),  # Convert UUID to string for serialization
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Message:
        """Create message from dictionary."""
        from utils.timezone_utils import parse_utc_time_string
        
        created_at = utc_now()
        if "created_at" in data:
            created_at = parse_utc_time_string(data["created_at"])
        
        return cls(
            id=UUID(data["id"]),  # ID is required, convert string to UUID
            role=data["role"],
            content=data["content"],
            created_at=created_at,
            metadata=data.get("metadata", {})
        )
    
    def with_metadata(self, **metadata_updates: object) -> Message:
        """Return new message with updated metadata."""
        new_metadata = {**self.metadata, **metadata_updates}
        return Message(
            id=self.id,
            role=self.role,
            content=self.content,
            created_at=self.created_at,
            metadata=new_metadata
        )
    
    def to_db_tuple(self, continuum_id: UUID, user_id: str) -> tuple[UUID, UUID, str, str, str, str, datetime]:
        """Convert to tuple for database insertion - UUIDs handled by PostgresClient."""
        import json
        return (
            self.id,  # Keep as UUID - PostgresClient will convert
            continuum_id,  # Keep as UUID - PostgresClient will convert
            user_id,
            self.role,
            self.content if isinstance(self.content, str) else json.dumps(self.content),
            json.dumps(self.metadata) if self.metadata else '{}',  # Serialize metadata to JSON, empty object if None
            self.created_at
        )