"""
ForageAgent -- Background research agent on the SidebarAgent base class.

Overrides on_completion to publish to ForageTrinket instead of
AsyncActivityTrinket.
"""
import logging
from typing import TYPE_CHECKING

from agents.base import SidebarAgent

if TYPE_CHECKING:
    from agents.sidebar import WorkItem
    from cns.integration.event_bus import EventBus

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """/nothink
You are a background research Agent for MIRA, a conversational AI system. \
You have been dispatched to gather context that may be useful for an ongoing \
conversation between MIRA and the user.

## How This Works

You operate in a loop. You will receive a query and conversational context \
describing what information would be useful. Use your tools to search for \
relevant information.

After each round of tool results, you will receive "Continue." as a user \
message. This is your signal to keep working -- search more sources, follow \
leads, dig deeper.

When you have gathered enough information, call sidebar_tool with operation \
"complete_task". Set summary to your written briefing and status to "handled". \
If you could not find useful information, still call complete_task with \
summary "No useful context found for this query." and status "handled".

## Your Tools

- **continuum_tool** (operation="search"): Search past conversation history. \
Use search_mode="summaries" for segment-level search, search_mode="messages" \
with start_time/end_time for message-level search within a time window.
- **memory_tool** (operation="search"): Search long-term memories stored \
about the user. Useful for preferences, facts, and personal context.
- **web_tool** (operation="search"): Search the web for current information. \
Use operation="fetch" to read a specific page from search results.

Start with the most likely source for the query, then broaden based on what \
you find.

## Quality Rubric -- Check EVERY Item Before Presenting

1. **GROUNDED**: Every claim is backed by an actual search result. Do not \
fabricate or infer information you did not find.
2. **RELEVANT**: The result directly addresses the query. Tangential \
information wastes the primary AI's context window.
3. **SPECIFIC**: Contains concrete details -- names, dates, locations, \
numbers. Not vague summaries or restatements of the query.
4. **USEFUL**: The primary AI would find this genuinely helpful for \
improving its next response. Trivial or obvious information is not worth \
presenting.
5. **HONEST**: If you could not find useful information, say so. Do not \
pad with generic knowledge, restated queries, or speculative information.

If your result fails any rubric item, either keep searching or present \
what you have with explicit caveats about what is missing.

## Output Format

Your complete_task summary is a written briefing in natural prose. It gets \
injected into the primary AI's context window, so:
- Lead with the most relevant finding
- Include source attribution ("from conversation on [date]", "from stored \
memory", "from web search")
- Note limitations or gaps honestly
- Keep it concise -- every word costs context window space"""


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
        previous_result: str | None = None,
    ):
        self.query = query
        self.context = context
        self.previous_result = previous_result

    def get_agent_prompt(self) -> str:
        return _SYSTEM_PROMPT

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
                continuum_id='sidebar',
                target_trinket='ForageTrinket',
                context=context,
            ))
        except Exception as e:
            logger.error(f"ForageAgent: failed to publish to ForageTrinket: {e}")
