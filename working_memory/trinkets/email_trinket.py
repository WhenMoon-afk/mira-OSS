"""
EmailTrinket — Renders inbox status in the HUD during active conversation
segments.

Thin StatefulTrinket. Zero I/O — receives inbox data from InboxPollerService
via UpdateTrinketEvent events, stores it in memory, renders XML. Cleared
automatically on segment collapse via WorkingMemory._flush_stateful_trinkets().
"""
import logging
from typing import Any, Dict, TYPE_CHECKING

from working_memory.trinkets.base import StatefulTrinket

if TYPE_CHECKING:
    from cns.integration.event_bus import EventBus
    from working_memory.core import WorkingMemory

logger = logging.getLogger(__name__)


class EmailTrinket(StatefulTrinket):
    """Displays unread email headers in the HUD notification center."""

    variable_name = "inbox_status"

    def __init__(self, event_bus: 'EventBus', working_memory: 'WorkingMemory'):
        super().__init__(event_bus, working_memory)
        self._inbox_snapshot: list[dict] = []

    def handle_update_request(self, event) -> None:
        """Store inbox data from poller, then delegate to parent for rendering.

        Two call paths arrive here:
        1. InboxPollerService publishes with context={'data': [...]}: store the
           snapshot, then render.
        2. Lifecycle refresh from ComposeSystemPromptEvent broadcast or
           StatefulTrinket expiry: no 'data' key, just re-render from
           existing snapshot.
        """
        data = event.context.get('data')
        if data is not None:
            self._inbox_snapshot = data

        super().handle_update_request(event)

    def generate_content(self, context: Dict[str, Any]) -> str:
        """Render inbox snapshot as XML for the HUD."""
        if not self._inbox_snapshot:
            return ""

        count = len(self._inbox_snapshot)
        lines = [
            '<inbox_status>',
            '<instruction>You have unread emails. Mention them to the user '
            'when the conversation permits — they cannot see this data unless '
            'you surface it. If they don\'t act, these will continue appearing.'
            '</instruction>',
            f'<unread count="{count}">',
        ]

        for em in self._inbox_snapshot:
            # Escape XML-sensitive chars in user-controlled content
            from_attr = _xml_attr_escape(em.get('from_addr', ''))
            subject_attr = _xml_attr_escape(em.get('subject', ''))
            date_attr = _xml_attr_escape(em.get('date', ''))
            uid_attr = _xml_attr_escape(em.get('uid', ''))

            lines.append(
                f'<email uid="{uid_attr}" from="{from_attr}" '
                f'subject="{subject_attr}" date="{date_attr}"/>'
            )

        lines.append('</unread>')
        lines.append('</inbox_status>')

        return '\n'.join(lines)

    def _expire_items(self) -> bool:
        """No turn-based expiry — inbox state is refreshed by the poller."""
        return False

    def _clear_all_state(self) -> None:
        """Clear inbox snapshot on segment collapse."""
        if self._inbox_snapshot:
            logger.debug(
                f"Clearing {len(self._inbox_snapshot)} inbox items "
                "on segment collapse"
            )
        self._inbox_snapshot.clear()


def _xml_attr_escape(value: str) -> str:
    """Escape a string for safe use inside an XML attribute value."""
    return (
        value
        .replace('&', '&amp;')
        .replace('"', '&quot;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )
