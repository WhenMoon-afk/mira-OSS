"""
Peanut Gallery metacognitive observer trinket.

Displays guidance messages from the Peanut Gallery observer system in the
notification center (HUD). Supports concern alerts and coaching suggestions
with turn-based TTL expiry.
"""
import logging
from dataclasses import dataclass
from typing import Dict, List, Literal, Any, TypedDict
from uuid import uuid4

from working_memory.trinkets.base import StatefulTrinket


class ActiveGuidance(TypedDict):
    """Active guidance entry returned by get_active_guidance()."""
    id: str
    type: Literal["concern", "coaching"]
    text: str
    turns_remaining: int

logger = logging.getLogger(__name__)


@dataclass
class GuidanceEntry:
    """A single guidance message with TTL tracking."""
    id: str
    guidance_type: Literal["concern", "coaching"]
    text: str
    expires_at_turn: int


class PeanutGalleryTrinket(StatefulTrinket):
    """
    Displays metacognitive guidance from the Peanut Gallery observer.

    Guidance automatically expires after a configurable number of turns (TTL)
    and is cleared entirely when the segment collapses (via WorkingMemory flush).
    """

    variable_name = "peanutgallery_guidance"

    def __init__(self, event_bus, working_memory, default_ttl: int = 5):
        """
        Initialize with state tracking.

        Args:
            event_bus: CNS event bus for publishing content
            working_memory: Working memory instance for registration
            default_ttl: Default turns until guidance expires
        """
        super().__init__(event_bus, working_memory)

        self._active_guidance: Dict[str, GuidanceEntry] = {}
        self._default_ttl = default_ttl

        logger.info(f"PeanutGalleryTrinket initialized with {default_ttl}-turn default TTL")

    def _expire_items(self) -> bool:
        """Remove guidance entries past their TTL."""
        expired = [
            gid for gid, entry in self._active_guidance.items()
            if self.current_turn > entry.expires_at_turn
        ]

        for gid in expired:
            del self._active_guidance[gid]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired guidance entries")

        return bool(expired)

    def _clear_all_state(self) -> None:
        """Clear all guidance entries."""
        if self._active_guidance:
            logger.info(f"Clearing {len(self._active_guidance)} guidance entries on segment collapse")
        self._active_guidance.clear()

    def get_active_guidance(self) -> list[ActiveGuidance]:
        """Get all currently active (non-expired) guidance messages."""
        return [
            {
                "id": entry.id,
                "type": entry.guidance_type,
                "text": entry.text,
                "turns_remaining": max(0, entry.expires_at_turn - self.current_turn)
            }
            for entry in self._active_guidance.values()
            if self.current_turn <= entry.expires_at_turn
        ]

    def add_guidance(
        self,
        guidance_type: Literal["concern", "coaching"],
        text: str,
        ttl: int | None = None
    ) -> str:
        """
        Add a new guidance message.

        Returns:
            Unique guidance ID
        """
        guidance_id = str(uuid4())[:8]
        ttl = ttl if ttl is not None else self._default_ttl

        self._active_guidance[guidance_id] = GuidanceEntry(
            id=guidance_id,
            guidance_type=guidance_type,
            text=text,
            expires_at_turn=self.current_turn + ttl
        )

        logger.info(f"Added {guidance_type} guidance (id={guidance_id}, ttl={ttl})")
        return guidance_id

    def handle_update_request(self, event) -> None:
        """Process incoming guidance from PeanutGalleryService."""
        context = event.context
        if context.get('action') == 'add_guidance':
            guidance_type = context.get('type')
            text = context.get('text')
            if guidance_type and text:
                self.add_guidance(guidance_type, text, context.get('ttl'))

        super().handle_update_request(event)

    def generate_content(self, context: Dict[str, Any]) -> str:
        """Generate HUD content showing all active guidance."""
        active = self.get_active_guidance()
        if not active:
            return ""

        parts = ['<mira:peanutgallery>']
        for guidance in active:
            parts.append(
                f'  <guidance type="{guidance["type"]}" expires_in="{guidance["turns_remaining"]}_turns">'
                f'{guidance["text"]}'
                f'</guidance>'
            )
        parts.append('</mira:peanutgallery>')
        return "\n".join(parts)
