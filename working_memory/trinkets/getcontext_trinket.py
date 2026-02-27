"""
GetContext search results trinket.

Displays asynchronous context search results when they become available.
Handles multiple concurrent searches, displays errors for 5 turns,
and clears all state on segment collapse.
"""
import logging
from typing import Dict, Any, TYPE_CHECKING

from working_memory.trinkets.base import StatefulTrinket

if TYPE_CHECKING:
    from cns.integration.event_bus import EventBus
    from working_memory.core import WorkingMemory

logger = logging.getLogger(__name__)


class GetContextTrinket(StatefulTrinket):
    """
    Displays context search results from getcontext_tool.

    This trinket:
    - Handles multiple concurrent searches in the same segment
    - Displays success results until segment collapse
    - Displays error/timeout messages for 5 turns
    - Clears all state when segment collapses (via WorkingMemory flush)
    """

    variable_name = "context_search_results"

    def __init__(self, event_bus: 'EventBus', working_memory: 'WorkingMemory'):
        """Initialize with state tracking."""
        super().__init__(event_bus, working_memory)
        self.active_results = {}  # task_id -> {type, data, received_turn, display_until_turn}
        logger.info("GetContextTrinket initialized with multi-result support")

    def _expire_items(self) -> bool:
        """Remove error/timeout results past their display window."""
        expired = [
            task_id for task_id, result in self.active_results.items()
            if result['type'] in ['timeout', 'failed']
            and self.current_turn > result.get('display_until_turn', 0)
        ]

        for task_id in expired:
            del self.active_results[task_id]
            logger.debug(f"Cleaned up expired error for task {task_id[:8]}")

        return bool(expired)

    def _clear_all_state(self) -> None:
        """Clear all search results."""
        if self.active_results:
            logger.info(f"Clearing {len(self.active_results)} search results on segment collapse")
        self.active_results.clear()

    def handle_update_request(self, event) -> None:
        """
        Process incoming search results (success/timeout/failure).

        Stores result in active_results state, then triggers content generation.
        This allows multiple searches to accumulate and display together.
        """
        context = event.context
        task_id = context.get('task_id')
        status = context.get('status', 'success')

        if not task_id:
            logger.warning("Received update without task_id, ignoring")
            return

        # Store result in state based on type
        if status == 'pending':
            self.active_results[task_id] = {
                'type': 'pending',
                'data': context,
                'received_turn': self.current_turn
            }
            logger.debug(f"Stored pending result for task {task_id[:8]}")

        elif status == 'success':
            self.active_results[task_id] = {
                'type': 'success',
                'data': context['summary'],
                'received_turn': self.current_turn
            }
            logger.debug(f"Stored success result for task {task_id[:8]}")

        elif status == 'timeout':
            self.active_results[task_id] = {
                'type': 'timeout',
                'data': context,
                'received_turn': self.current_turn,
                'display_until_turn': self.current_turn + 5
            }
            logger.debug(f"Stored timeout result for task {task_id[:8]}, will display for 5 turns")

        elif status == 'failed':
            self.active_results[task_id] = {
                'type': 'failed',
                'data': context,
                'received_turn': self.current_turn,
                'display_until_turn': self.current_turn + 5
            }
            logger.debug(f"Stored failure result for task {task_id[:8]}, will display for 5 turns")

        # Trigger content generation and publication
        super().handle_update_request(event)

    def generate_content(self, context: Dict[str, Any]) -> str:
        """
        Generate content showing ALL active search results.

        Formats successes and currently-visible errors with clear separation.
        Context parameter is ignored - we format all active state.
        """
        parts = []

        # Collect all displayable results
        for task_id, result in list(self.active_results.items()):
            if result['type'] == 'pending':
                parts.append(self._format_pending_result(result['data']))

            elif result['type'] == 'success':
                parts.append(self._format_success_result(result['data']))

            elif result['type'] in ['timeout', 'failed']:
                # Only show if still within display window
                if self.current_turn <= result.get('display_until_turn', 0):
                    parts.append(self._format_error_result(result))

        # Wrap in XML structure
        if parts:
            return "<context_search_results>\n" + "\n".join(parts) + "\n</context_search_results>"

        return ""

    def _format_success_result(self, summary: Dict[str, Any]) -> str:
        """Format successful search results as XML."""
        query = summary.get('query', 'Unknown query')
        parts = [f'<result type="success" query="{query}">']

        # Summary content
        summary_text = summary.get('summary', '')
        if summary_text:
            parts.append(f"<summary>{summary_text}</summary>")

        # Key findings
        key_findings = summary.get('key_findings', [])
        if key_findings:
            parts.append("<findings>")
            for finding in key_findings:
                point = finding.get('point', '')
                source = finding.get('source', '')
                if source:
                    parts.append(f'<finding source="{source}">{point}</finding>')
                else:
                    parts.append(f"<finding>{point}</finding>")
            parts.append("</findings>")

        # Limitations
        if summary.get('limitations'):
            parts.append(f"<limitations>{summary['limitations']}</limitations>")

        parts.append("</result>")
        return "\n".join(parts)

    def _format_error_result(self, result: Dict[str, Any]) -> str:
        """Format error result as XML with remaining display time."""
        data = result['data']
        result_type = result['type']
        turns_remaining = result['display_until_turn'] - self.current_turn

        if result_type == 'timeout':
            return (
                f'<result type="timeout" query="{data["query"]}" turns_remaining="{turns_remaining}">\n'
                f"<warning>⚠️ Context search timed out</warning>\n"
                f"<details>The search exceeded 5 minutes (stopped at iteration {data['iteration']} "
                f"with {data['findings_count']} findings).</details>\n"
                f"<guidance>Try rephrasing your query or tell the user the search was inconclusive.</guidance>\n"
                f"</result>"
            )
        else:  # failed
            return (
                f'<result type="failed" query="{data["query"]}" turns_remaining="{turns_remaining}">\n'
                f"<warning>⚠️ Context search failed</warning>\n"
                f"<error type=\"{data['error_type']}\">{data['error']}</error>\n"
                f"<guidance>Try rephrasing the query or tell the user you encountered an error.</guidance>\n"
                f"</result>"
            )

    def _format_pending_result(self, data: Dict[str, Any]) -> str:
        """Format pending/searching result as XML."""
        query = data.get('query', 'Unknown query')
        search_scope = data.get('search_scope', [])
        search_mode = data.get('search_mode', 'standard')

        scope_text = ', '.join(search_scope) if search_scope else 'all sources'

        return (
            f'<result type="pending" query="{query}" search_mode="{search_mode}" sources="{scope_text}">\n'
            f"<status>Results will appear here when the search completes...</status>\n"
            f"</result>"
        )
