"""
ForageAgent -- Background research agent on the SidebarAgent base class.

Overrides on_completion to publish to ForageTrinket instead of
AsyncActivityTrinket.
"""
import logging
from typing import TYPE_CHECKING

from agents.base import SidebarAgent, load_agent_prompt

if TYPE_CHECKING:
    from agents.sidebar import WorkItem
    from cns.integration.event_bus import EventBus

logger = logging.getLogger(__name__)


class ForageAgent(SidebarAgent):
    agent_id = "forage"
    internal_llm_key = "forage"
    available_tools = ["continuum_tool", "memory_tool", "web_tool"]
    inherit_base_prompt = False
    max_iterations = 12
    timeout_seconds = 120

    def __init__(
        self,
        query: str,
        context: str,
        continuum_id: str = 'sidebar',
        previous_result: str | None = None,
    ):
        self.query = query
        self.context = context
        self.continuum_id = continuum_id
        self.previous_result = previous_result

    def get_agent_prompt(self, work_item: 'WorkItem') -> str:
        return load_agent_prompt("forage_system.txt")

    def build_initial_message(self, work_item: 'WorkItem') -> str:
        if self.previous_result:
            return (
                f"**Previous forage result (you are refining this):**\n"
                f"{self.previous_result}\n\n"
                f"**Refinement:** {self.query}\n\n"
                f"**Context:** {self.context}\n\n"
                "The previous search found the above. Refine, correct, or "
                "dig deeper based on the refinement instruction. Build on "
                "what was found -- don't repeat the same searches."
            )
        return (
            f"**Query:** {self.query}\n\n"
            f"**Context:** {self.context}\n\n"
            "Search for information relevant to this query. "
            "Use the context to understand what would be most useful."
        )

    def on_completion(
        self,
        event_bus: 'EventBus',
        work_item: 'WorkItem',
        status: str,
        summary: str,
    ) -> None:
        """Publish to ForageTrinket instead of AsyncActivityTrinket."""
        from cns.core.events import UpdateTrinketEvent

        status_map = {
            'success': 'success',
            'timeout': 'timeout',
            'failed': 'failed',
        }
        trinket_status = status_map.get(status, 'failed')

        context: dict = {
            'task_id': work_item.item_id,
            'status': trinket_status,
            'query': self.query,
        }

        if trinket_status == 'success':
            context['result'] = summary
        else:
            context['error'] = summary
            context['error_type'] = 'AgentFailure'

        try:
            event_bus.publish(UpdateTrinketEvent.create(
                continuum_id=self.continuum_id,
                target_trinket='ForageTrinket',
                context=context,
            ))
        except Exception as e:
            logger.error(
                f"ForageAgent: failed to publish to ForageTrinket: {e}",
                exc_info=True,
            )
