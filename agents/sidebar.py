"""
Sidebar Dispatcher -- Trigger protocol, WorkItem, and dispatch loop.

Single APScheduler IntervalTrigger job. On each tick: iterates users with
sidebar-eligible configs, iterates registered triggers, spawns agent
threads with copied user context.
"""
import logging
import threading
from contextvars import copy_context
from typing import Any, Protocol, runtime_checkable, TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from agents.base import SidebarAgent
    from tools.repo import ToolRepository
    from cns.integration.event_bus import EventBus

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------
# Data types
# -----------------------------------------------------------------------

class WorkItem(BaseModel):
    """A unit of work detected by a trigger."""
    item_id: str         # Unique ID for dedup (e.g. email Message-ID)
    interface_name: str  # Key for AsyncActivityTrinket (e.g. "email_watcher")
    context: dict[str, Any]  # Trigger-specific payload passed to the agent


# -----------------------------------------------------------------------
# Trigger protocol
# -----------------------------------------------------------------------

@runtime_checkable
class SidebarTrigger(Protocol):
    trigger_id: str
    interface_name: str
    agent_class: type['SidebarAgent']

    def check_for_new_items(self, user_id: str) -> list[WorkItem]:
        """Poll for new work. Dedup is the trigger's responsibility."""
        ...

    def mark_processed(self, user_id: str, item_id: str) -> None:
        """Mark an item as handled to prevent re-dispatch."""
        ...


# -----------------------------------------------------------------------
# Dispatcher
# -----------------------------------------------------------------------

# Per-user-per-poll cap to prevent runaway cost from misconfigured triggers
MAX_ITEMS_PER_USER_PER_POLL = 5


class SidebarDispatcher:
    """Iterates users and triggers, spawns sidebar agent threads."""

    def __init__(
        self,
        tool_repo: 'ToolRepository',
        event_bus: 'EventBus',
        max_concurrent_agents: int = 3,
    ):
        self.tool_repo = tool_repo
        self.event_bus = event_bus
        self.max_concurrent_agents = max_concurrent_agents
        self._triggers: list[SidebarTrigger] = []
        self._active_threads: list[threading.Thread] = []

    def register_trigger(self, trigger: SidebarTrigger) -> None:
        self._triggers.append(trigger)
        logger.info(f"Registered sidebar trigger: {trigger.trigger_id}")

    def poll(self) -> None:
        """Single poll cycle. Called by APScheduler on each tick."""
        from utils.user_context import set_current_user_id, clear_user_context

        # Prune finished threads
        self._active_threads = [
            t for t in self._active_threads if t.is_alive()
        ]

        users = self._get_eligible_users()
        if not users:
            return

        for user in users:
            user_id = str(user['id'])
            set_current_user_id(user_id)
            try:
                self._poll_user(user_id)
            except Exception as e:
                logger.error(
                    f"Sidebar dispatcher error for user {user_id}: {e}",
                    exc_info=True,
                )
            finally:
                clear_user_context()

    def _poll_user(self, user_id: str) -> None:
        """Check all triggers for a single user."""
        for trigger in self._triggers:
            try:
                items = trigger.check_for_new_items(user_id)
                if not items:
                    continue

                # Cap per-user-per-poll
                items = items[:MAX_ITEMS_PER_USER_PER_POLL]

                for item in items:
                    if len(self._active_threads) >= self.max_concurrent_agents:
                        logger.info(
                            "Sidebar dispatcher: concurrent agent limit reached"
                        )
                        return

                    self._spawn_agent(trigger, item, user_id)
                    trigger.mark_processed(user_id, item.item_id)

            except Exception as e:
                logger.error(
                    f"Trigger {trigger.trigger_id} failed for user "
                    f"{user_id}: {e}",
                    exc_info=True,
                )

    def _spawn_agent(
        self,
        trigger: SidebarTrigger,
        item: WorkItem,
        user_id: str,
    ) -> None:
        """Spawn agent in background thread with copied user context."""
        agent = trigger.agent_class()
        ctx = copy_context()

        thread = threading.Thread(
            target=ctx.run,
            args=(agent.run, item, self.tool_repo, self.event_bus),
            name=f"sidebar-{trigger.trigger_id}-{item.item_id[:8]}",
            daemon=True,
        )
        thread.start()
        self._active_threads.append(thread)
        logger.info(
            f"Spawned {trigger.agent_class.agent_id} for "
            f"{item.interface_name}:{item.item_id[:8]}"
        )

    def _get_eligible_users(self) -> list[dict]:
        """Get users who have sidebar triggers configured."""
        from utils.database_session_manager import get_shared_session_manager

        session_manager = get_shared_session_manager()
        with session_manager.get_admin_session() as session:
            return session.execute_query("""
                SELECT id FROM users
                WHERE is_active = TRUE
                AND last_activity_date >= CURRENT_DATE - INTERVAL '2 days'
            """)
