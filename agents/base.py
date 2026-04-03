"""
SidebarAgent -- Base class for autonomous sidebar agents.

Encapsulates LLM-in-a-loop mechanics so implementations only define
domain logic: prompt, initial message, and tool list.

Loop terminates when the LLM calls sidebar_tool.complete_task().
The base class intercepts that call, enriches it with work item metadata,
executes the tool (which writes the activity record to SQLite), publishes
an UpdateTrinketEvent to refresh the AsyncActivityTrinket, and exits.
"""
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TYPE_CHECKING
from typing_extensions import TypedDict

from clients.llm_provider import LLMProvider
from utils.timezone_utils import utc_now, format_utc_iso

if TYPE_CHECKING:
    from agents.sidebar import WorkItem
    from tools.repo import ToolRepository
    from cns.integration.event_bus import EventBus

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------
# Base prompt -- prepended when inherit_base_prompt is True.
# Describes the loop mechanics so the LLM knows how the agent works.
# Agent-specific rubric from get_agent_prompt() is appended after.
# -----------------------------------------------------------------------

_BASE_PROMPT = """\
You are Mira, operating as an autonomous sidebar agent -- handling a \
specific task independently while the main conversation may or may not \
be active.

You operate in a loop. After each round of tool calls, you will receive \
"Continue." as a user message. This is your signal to keep working -- \
review results, take further action, or finish up.

When you have completed your task, you MUST call sidebar_tool with \
operation "complete_task" and provide a summary of what you did plus a \
status. This is the only way to finish -- the absence of tool calls \
does NOT signal completion.

Maintain Mira's voice: direct, warm, human. Not corporate, not generic."""


# -----------------------------------------------------------------------
# Shared DDL -- used by SidebarAgent (failure records) and sidebar_tool
# (complete_task records). Both call CREATE TABLE IF NOT EXISTS.
# -----------------------------------------------------------------------

ACTIVITY_TABLE_DDL = """\
CREATE TABLE IF NOT EXISTS sidebar_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interface_name TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'handled',
    escalation_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(interface_name, thread_id)
)"""

ACTIVITY_INDEX_DDL = """\
CREATE INDEX IF NOT EXISTS idx_activity_interface
ON sidebar_activity(interface_name)"""


# -----------------------------------------------------------------------
# Structured types for trace data
# -----------------------------------------------------------------------

class ToolCallTrace(TypedDict):
    tool_name: str
    input: dict[str, Any]
    result: Any
    is_error: bool


class IterationTrace(TypedDict):
    iteration: int
    assistant_text: str
    tool_calls: list[ToolCallTrace]


class AgentTrace(TypedDict):
    agent_id: str
    work_item_id: str
    interface_name: str
    model: str | None
    started_at: str
    completed_at: str
    total_iterations: int
    iterations: list[IterationTrace]
    status: str | None


# -----------------------------------------------------------------------
# SidebarAgent ABC
# -----------------------------------------------------------------------

class SidebarAgent(ABC):
    """
    Abstract base class for autonomous sidebar agents.

    Implementations define:
        agent_id         -- unique identifier (e.g. "email_sidebar")
        internal_llm_key -- key into internal_llm DB table
        available_tools  -- domain-specific tool names from registry
                            (sidebar_tool is always included automatically)
        get_agent_prompt()          -> str  -- agent-specific rubric
        build_initial_message(item) -> str  -- first user message

    The base class owns: LLM init, tool schema assembly (always includes
    sidebar_tool + implementation tools), message loop with heartbeat,
    tool execution, complete_task detection, trace capture, and activity
    publishing.
    """

    # Required -- subclasses must define
    agent_id: str
    internal_llm_key: str
    available_tools: list[str]

    # Optional -- subclasses override as needed
    inherit_base_prompt: bool = True
    max_iterations: int = 5
    timeout_seconds: int = 120

    # Per-tool schema overrides. Maps tool name → custom anthropic_schema.
    # Used to restrict tool capabilities for sidebar agents (e.g.
    # email_tool → reply_to_email only).
    tool_schema_overrides: dict[str, dict] = {}

    @abstractmethod
    def get_agent_prompt(self) -> str:
        """Return the agent-specific system prompt / rubric."""
        ...

    @abstractmethod
    def build_initial_message(self, work_item: 'WorkItem') -> str:
        """Build the initial user message from the work item context."""
        ...

    def get_heartbeat(self, iteration: int) -> str:
        """Heartbeat injected as user message between iterations."""
        return "Continue."

    # ------------------------------------------------------------------
    # Completion publication -- override to target a different trinket
    # ------------------------------------------------------------------

    def on_completion(
        self,
        event_bus: 'EventBus',
        work_item: 'WorkItem',
        status: str,
        summary: str,
    ) -> None:
        """Called after agent completes (success or failure).

        Default publishes to AsyncActivityTrinket. Override to publish
        to a different trinket (e.g. ForageAgent → ForageTrinket).
        """
        _publish_trinket_refresh(event_bus)

    # ------------------------------------------------------------------
    # System prompt assembly
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        agent_prompt = self.get_agent_prompt()
        if not self.inherit_base_prompt:
            return agent_prompt
        return f"{_BASE_PROMPT}\n\n{agent_prompt}"

    # ------------------------------------------------------------------
    # Tool schema assembly
    # ------------------------------------------------------------------

    def _get_all_tool_names(self) -> list[str]:
        """sidebar_tool is always included; subclass tools are appended."""
        names = ['sidebar_tool']
        for name in self.available_tools:
            if name not in names:
                names.append(name)
        return names

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(
        self,
        work_item: 'WorkItem',
        tool_repo: 'ToolRepository',
        event_bus: 'EventBus',
    ) -> None:
        """Execute the agent loop. Implementations should not override this."""
        from utils.user_context import get_internal_llm
        from clients.vault_client import get_api_key

        start_time = utc_now()
        trace = _init_trace(self.agent_id, work_item, start_time)

        try:
            # Tool schemas -- sidebar_tool always included
            all_tool_names = self._get_all_tool_names()
            tool_schemas = _get_tool_schemas(
                tool_repo, all_tool_names, self.agent_id,
                self.tool_schema_overrides,
            )
            if not tool_schemas:
                logger.warning(f"{self.agent_id}: No tools available")
                trace['status'] = 'failed'
                _write_failure_activity(
                    work_item, self.agent_id, 'No tools available'
                )
                self.on_completion(
                    event_bus, work_item, 'failed', 'No tools available'
                )
                return

            # LLM config
            llm_cfg = get_internal_llm(self.internal_llm_key)
            api_key = (
                get_api_key(llm_cfg.api_key_name)
                if llm_cfg.api_key_name else None
            )
            llm = LLMProvider(max_tokens=llm_cfg.max_tokens)
            trace['model'] = llm_cfg.model

            system_prompt = self._build_system_prompt()
            messages: list[dict[str, Any]] = [{
                "role": "user",
                "content": self.build_initial_message(work_item),
            }]

            for iteration in range(1, self.max_iterations + 1):
                # Timeout gate
                elapsed = (utc_now() - start_time).total_seconds()
                if elapsed > self.timeout_seconds:
                    logger.warning(
                        f"{self.agent_id}: Timed out at iteration {iteration}"
                    )
                    trace['status'] = 'timeout'
                    timeout_msg = f'Agent timed out after {elapsed:.0f}s'
                    _write_failure_activity(
                        work_item, self.agent_id, timeout_msg,
                    )
                    self.on_completion(
                        event_bus, work_item, 'timeout', timeout_msg
                    )
                    return

                # LLM call
                response = llm.generate_response(
                    messages=messages,
                    tools=tool_schemas,
                    endpoint_url=llm_cfg.endpoint_url,
                    model_override=llm_cfg.model,
                    api_key_override=api_key,
                    system_override=system_prompt,
                )

                tool_calls = llm.extract_tool_calls(response)
                assistant_text = llm.extract_text_content(response)

                # No tool calls -- nudge the agent to complete_task
                if not tool_calls:
                    trace['iterations'].append(IterationTrace(
                        iteration=iteration,
                        assistant_text=assistant_text,
                        tool_calls=[],
                    ))
                    messages.append({
                        "role": "assistant",
                        "content": _serialize_response(response),
                    })
                    messages.append({
                        "role": "user",
                        "content": (
                            "You must call sidebar_tool complete_task to "
                            "finish your work."
                        ),
                    })
                    continue

                messages.append({
                    "role": "assistant",
                    "content": _serialize_response(response),
                })

                # Execute tool calls, detect complete_task
                tool_results: list[dict[str, Any]] = []
                completed = False

                for tc in tool_calls:
                    is_complete = (
                        tc['tool_name'] == 'sidebar_tool'
                        and tc['input'].get('operation') == 'complete_task'
                    )
                    if is_complete:
                        tc['input']['thread_id'] = work_item.item_id
                        tc['input']['interface_name'] = work_item.interface_name
                        tc['input']['agent_id'] = self.agent_id

                    # Enrich email_tool replies with task ID for guardrails
                    is_sidebar_reply = (
                        tc['tool_name'] == 'email_tool'
                        and tc['input'].get('operation') == 'reply_to_email'
                    )
                    if is_sidebar_reply:
                        tc['input']['sidebar_task_id'] = work_item.item_id

                    result = _execute_tool_call(
                        tool_repo, tc, self.agent_id
                    )
                    tool_results.append(result)

                    if is_complete and not result.get('is_error'):
                        completed = True

                # Trace
                trace['iterations'].append(IterationTrace(
                    iteration=iteration,
                    assistant_text=assistant_text,
                    tool_calls=[
                        ToolCallTrace(
                            tool_name=tc['tool_name'],
                            input=tc['input'],
                            result=_parse_result(tr['content']),
                            is_error=tr.get('is_error', False),
                        )
                        for tc, tr in zip(tool_calls, tool_results)
                    ],
                ))

                if completed:
                    trace['status'] = 'success'
                    # Extract summary from the complete_task result
                    complete_result = _parse_result(
                        tool_results[-1]['content']
                    )
                    summary = (
                        complete_result.get('summary', '')
                        if isinstance(complete_result, dict) else ''
                    )
                    self.on_completion(
                        event_bus, work_item, 'success', summary
                    )
                    return

                # Heartbeat
                if iteration == self.max_iterations:
                    heartbeat = (
                        f"You have hit the {self.max_iterations}-iteration "
                        "limit imposed on this agent. Call sidebar_tool "
                        "complete_task now with whatever you have. Summarize "
                        "what you accomplished and what remains."
                    )
                else:
                    heartbeat = self.get_heartbeat(iteration)

                messages.append({
                    "role": "user",
                    "content": tool_results + [
                        {"type": "text", "text": heartbeat}
                    ],
                })

            # Iteration cap hit without complete_task
            trace['status'] = 'failed'
            cap_msg = 'Agent hit iteration cap without completing'
            _write_failure_activity(
                work_item, self.agent_id, cap_msg,
            )
            self.on_completion(event_bus, work_item, 'failed', cap_msg)

        except Exception as e:
            logger.error(f"{self.agent_id}: Failed: {e}", exc_info=True)
            trace['status'] = 'failed'
            err_msg = f'Agent error: {e}'
            _write_failure_activity(
                work_item, self.agent_id, err_msg
            )
            self.on_completion(event_bus, work_item, 'failed', err_msg)

        finally:
            trace['completed_at'] = format_utc_iso(utc_now())
            trace['total_iterations'] = len(trace['iterations'])
            _save_trace(self.agent_id, work_item.item_id, trace)


# -----------------------------------------------------------------------
# Module-level helpers
# -----------------------------------------------------------------------

def _init_trace(
    agent_id: str, work_item: 'WorkItem', start_time: Any
) -> dict[str, Any]:
    """Initialize trace dict. completed_at and total_iterations set in finally."""
    return {
        'agent_id': agent_id,
        'work_item_id': work_item.item_id,
        'interface_name': work_item.interface_name,
        'model': None,
        'started_at': format_utc_iso(start_time),
        'iterations': [],
        'status': None,
    }


def _get_tool_schemas(
    tool_repo: 'ToolRepository',
    tool_names: list[str],
    agent_id: str,
    overrides: dict[str, dict] | None = None,
) -> list[dict[str, Any]]:
    schemas = []
    for tool_name in tool_names:
        if overrides and tool_name in overrides:
            schemas.append(overrides[tool_name])
            continue
        try:
            tool = tool_repo.get_tool(tool_name)
            if tool:
                schemas.append(tool.anthropic_schema)
        except Exception as e:
            logger.debug(f"{agent_id}: Tool {tool_name} unavailable: {e}")
    return schemas


def _serialize_response(response: Any) -> list[dict[str, Any]]:
    content = []
    for block in response.content:
        if block.type == "text":
            content.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            content.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    return content


def _execute_tool_call(
    tool_repo: 'ToolRepository',
    tc: dict[str, Any],
    agent_id: str,
) -> dict[str, Any]:
    try:
        tool = tool_repo.get_tool(tc['tool_name'])
        result = tool.run(**tc['input'])
        return {
            "type": "tool_result",
            "tool_use_id": tc['id'],
            "content": json.dumps(result, default=str),
        }
    except Exception as e:
        logger.warning(f"{agent_id}: Tool {tc['tool_name']} failed: {e}")
        return {
            "type": "tool_result",
            "tool_use_id": tc['id'],
            "content": json.dumps({"error": str(e)}),
            "is_error": True,
        }


def _parse_result(content: str) -> Any:
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return content


def _write_failure_activity(
    work_item: 'WorkItem',
    agent_id: str,
    summary: str,
) -> None:
    """Write a failure activity record to SQLite."""
    try:
        from utils.userdata_manager import get_user_data_manager
        from utils.user_context import get_current_user_id

        db = get_user_data_manager(get_current_user_id())
        db.execute(ACTIVITY_TABLE_DDL)
        db.execute(ACTIVITY_INDEX_DDL)
        db.execute(
            "INSERT OR REPLACE INTO sidebar_activity "
            "(interface_name, thread_id, agent_id, summary, status, updated_at) "
            "VALUES (:interface_name, :thread_id, :agent_id, :summary, "
            ":status, datetime('now'))",
            {
                'interface_name': work_item.interface_name,
                'thread_id': work_item.item_id,
                'agent_id': agent_id,
                'summary': summary,
                'status': 'failed',
            },
        )
    except Exception as e:
        logger.error(f"{agent_id}: Failed to write failure activity: {e}")


def _publish_trinket_refresh(event_bus: 'EventBus') -> None:
    """Publish UpdateTrinketEvent so AsyncActivityTrinket re-renders."""
    try:
        from cns.core.events import UpdateTrinketEvent
        event_bus.publish(UpdateTrinketEvent.create(
            continuum_id='sidebar',
            target_trinket='AsyncActivityTrinket',
            context={'action': 'refresh'},
        ))
    except Exception as e:
        logger.error(f"Failed to publish trinket refresh: {e}")


def _save_trace(
    agent_id: str, item_id: str, trace: dict[str, Any]
) -> None:
    try:
        from utils.userdata_manager import get_user_data_manager
        from utils.user_context import get_current_user_id

        db = get_user_data_manager(get_current_user_id())
        trace_dir = Path(db.get_tool_data_dir('sidebar_agent'))
        path = trace_dir / f"{item_id}.json"
        with open(path, 'w') as f:
            json.dump(trace, f, indent=2, default=str)
    except Exception as e:
        logger.warning(f"{agent_id}: Failed to save trace: {e}")
