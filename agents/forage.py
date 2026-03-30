"""
Forage Agent — Background research agent for speculative context gathering.

Operates in a loop: receives query + context, uses search tools to gather
information, and produces a written briefing when sufficient context is found.

Loop mechanism: the agent receives "Continue." as its only user message after
each round of tool results. It keeps working until it produces a final response
with no tool calls (signaling completion) or hits the iteration cap.
"""
import json
import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from clients.llm_provider import LLMProvider
from utils.timezone_utils import utc_now, format_utc_iso

if TYPE_CHECKING:
    from tools.repo import ToolRepository
    from cns.integration.event_bus import EventBus

logger = logging.getLogger(__name__)


# Tools the forage agent can use — sourced from ToolRepository at runtime
AVAILABLE_TOOLS = ['continuum_tool', 'memory_tool', 'web_tool']


SYSTEM_PROMPT = """/nothink
You are a background research Agent for MIRA, a conversational AI system. You have been dispatched to gather context that may be useful for an ongoing conversation between MIRA and the user.

## How This Works

You operate in a loop. You will receive a query and conversational context describing what information would be useful. Use your tools to search for relevant information.

After each round of tool results, you will receive "Continue." as your only user message. This is your signal to keep working — search more sources, follow leads, dig deeper.

When you have gathered enough information to produce a useful result, write your findings as a clear, concise briefing. Do NOT include any tool calls in your final response — the absence of tool calls signals that you are done.

## Your Tools

- **continuum_tool** (operation="search"): Search past conversation history. Use search_mode="summaries" for segment-level search, search_mode="messages" with start_time/end_time for message-level search within a time window.
- **memory_tool** (operation="search"): Search long-term memories stored about the user. Useful for preferences, facts, and personal context.
- **web_tool** (operation="search"): Search the web for current information. Use operation="fetch" to read a specific page from search results.

Start with the most likely source for the query, then broaden based on what you find.

## Quality Rubric — Check EVERY Item Before Presenting

1. **GROUNDED**: Every claim is backed by an actual search result. Do not fabricate or infer information you did not find.
2. **RELEVANT**: The result directly addresses the query. Tangential information wastes the primary AI's context window.
3. **SPECIFIC**: Contains concrete details — names, dates, locations, numbers. Not vague summaries or restatements of the query.
4. **USEFUL**: The primary AI would find this genuinely helpful for improving its next response. Trivial or obvious information is not worth presenting.
5. **HONEST**: If you could not find useful information, say "No useful context found for this query." Do not pad with generic knowledge, restated queries, or speculative information.

If your result fails any rubric item, either keep searching or present what you have with explicit caveats about what is missing.

## Output Format

Your final response is a written briefing in natural prose. It gets injected into the primary AI's context window, so:
- Lead with the most relevant finding
- Include source attribution ("from conversation on [date]", "from stored memory", "from web search")
- Note limitations or gaps honestly
- Keep it concise — every word costs context window space"""


def run(
    query: str,
    context: str,
    task_id: str,
    continuum_id: str,
    tool_repo: 'ToolRepository',
    event_bus: 'EventBus',
    config: Any,
    previous_result: Optional[str] = None,
    trace_dir: Optional[str] = None,
) -> None:
    """
    Run the forage agent loop. Called from a background thread.

    Publishes results to ForageTrinket via event bus on completion.
    Writes a trace file to trace_dir for observability.
    Handles its own error/timeout reporting — caller does not need
    to catch exceptions.

    Args:
        query: What to search for (or refinement instruction if previous_result)
        context: Conversational context motivating the search
        task_id: Unique identifier for this forage task
        continuum_id: User's continuum ID for event routing
        tool_repo: ToolRepository for accessing search tools
        event_bus: Event bus for publishing results to trinket
        config: ForageToolConfig with LLM and iteration settings
        previous_result: Written result from a prior forage to refine
        trace_dir: Directory to write trace file (one JSON per forage)
    """
    start_time = utc_now()
    iteration = 0

    # Trace captures every intermediate step for observability
    trace: Dict[str, Any] = {
        'task_id': task_id,
        'query': query,
        'context': context,
        'previous_result': previous_result,
        'model': config.llm_model,
        'started_at': format_utc_iso(start_time),
        'iterations': [],
        'status': None,
        'final_result': None,
    }

    try:
        # Build tool schemas from the live repository — same tools the primary LLM uses
        tool_schemas = _get_tool_schemas(tool_repo)
        if not tool_schemas:
            logger.warning(f"Forage {task_id[:8]}: No search tools available")
            trace['status'] = 'failed'
            trace['error'] = 'No search tools available in tool repository'
            _publish_result(event_bus, continuum_id, task_id, 'failed', {
                'query': query,
                'error': 'No search tools available in tool repository',
                'error_type': 'ConfigurationError',
            })
            return

        llm = LLMProvider()
        api_key = _get_api_key(config)

        # Build initial message — include previous result if refining
        if previous_result:
            initial_content = (
                f"**Previous forage result (you are refining this):**\n"
                f"{previous_result}\n\n"
                f"**Refinement:** {query}\n\n"
                f"**Context:** {context}\n\n"
                "The previous search found the above. Refine, correct, or dig "
                "deeper based on the refinement instruction. Build on what was "
                "found — don't repeat the same searches."
            )
        else:
            initial_content = (
                f"**Query:** {query}\n\n"
                f"**Context:** {context}\n\n"
                "Search for information relevant to this query. "
                "Use the context to understand what would be most useful."
            )

        messages: List[Dict[str, Any]] = [{
            "role": "user",
            "content": initial_content,
        }]

        written_result = None

        for iteration in range(1, config.max_iterations + 1):
            # Timeout check
            elapsed = (utc_now() - start_time).total_seconds()
            if elapsed > config.search_timeout_seconds:
                logger.warning(
                    f"Forage {task_id[:8]}: Timed out after {elapsed:.1f}s "
                    f"at iteration {iteration}"
                )
                trace['status'] = 'timeout'
                _publish_result(event_bus, continuum_id, task_id, 'timeout', {
                    'query': query,
                    'iteration': iteration,
                    'elapsed': elapsed,
                })
                return

            # Call LLM with tools
            logger.debug(f"Forage {task_id[:8]}: Iteration {iteration}")
            response = llm.generate_response(
                messages=messages,
                tools=tool_schemas,
                endpoint_url=config.llm_endpoint,
                model_override=config.llm_model,
                api_key_override=api_key,
                system_override=SYSTEM_PROMPT,
            )

            # Check if agent is done (no tool calls = final response)
            tool_calls = llm.extract_tool_calls(response)
            assistant_text = llm.extract_text_content(response)

            if not tool_calls:
                written_result = assistant_text
                trace['iterations'].append({
                    'iteration': iteration,
                    'assistant_text': assistant_text,
                    'tool_calls': [],
                })
                logger.info(
                    f"Forage {task_id[:8]}: Complete after {iteration} iterations "
                    f"({len(written_result)} chars)"
                )
                break

            # Agent wants to use tools — add its response to conversation
            messages.append({
                "role": "assistant",
                "content": _serialize_response_content(response),
            })

            # Execute tool calls
            tool_results = _execute_tool_calls(tool_repo, tool_calls, task_id)

            # Capture iteration trace
            trace['iterations'].append({
                'iteration': iteration,
                'assistant_text': assistant_text,
                'tool_calls': [
                    {
                        'tool_name': tc['tool_name'],
                        'input': tc['input'],
                        'result': _parse_tool_result(tr['content']),
                        'is_error': tr.get('is_error', False),
                    }
                    for tc, tr in zip(tool_calls, tool_results)
                ],
            })

            # Heartbeat: tool results + "Continue." (or final nudge on last iteration)
            if iteration < config.max_iterations:
                heartbeat = "Continue."
            else:
                heartbeat = (
                    "This is your final iteration. Present your findings now "
                    "based on what you have gathered so far."
                )

            messages.append({
                "role": "user",
                "content": tool_results + [{"type": "text", "text": heartbeat}],
            })

        # If we hit max iterations without a clean exit, force one more call
        if written_result is None:
            logger.info(
                f"Forage {task_id[:8]}: Hit iteration cap ({config.max_iterations}), "
                "forcing summary"
            )
            response = llm.generate_response(
                messages=messages,
                endpoint_url=config.llm_endpoint,
                model_override=config.llm_model,
                api_key_override=api_key,
                system_override=SYSTEM_PROMPT,
                # No tools — forces text-only response
            )
            written_result = llm.extract_text_content(response)
            trace['iterations'].append({
                'iteration': iteration + 1,
                'assistant_text': written_result,
                'tool_calls': [],
                'forced_summary': True,
            })

        # Publish success
        trace['status'] = 'success'
        trace['final_result'] = written_result
        _publish_result(event_bus, continuum_id, task_id, 'success', {
            'query': query,
            'result': written_result,
            'iterations': iteration,
            'elapsed': (utc_now() - start_time).total_seconds(),
        })

    except Exception as e:
        logger.error(f"Forage {task_id[:8]}: Failed: {e}", exc_info=True)
        trace['status'] = 'failed'
        trace['error'] = str(e)
        trace['error_type'] = type(e).__name__
        _publish_result(event_bus, continuum_id, task_id, 'failed', {
            'query': query,
            'error': str(e),
            'error_type': type(e).__name__,
        })

    finally:
        trace['completed_at'] = format_utc_iso(utc_now())
        trace['total_iterations'] = len(trace['iterations'])
        _save_trace(trace_dir, task_id, trace)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_tool_schemas(tool_repo: 'ToolRepository') -> List[Dict[str, Any]]:
    """Extract Anthropic-format tool schemas for available search tools."""
    schemas = []
    for tool_name in AVAILABLE_TOOLS:
        try:
            tool = tool_repo.get_tool(tool_name)
            if tool:
                schemas.append(tool.anthropic_schema)
        except Exception as e:
            logger.debug(f"Tool {tool_name} not available for forage: {e}")
    return schemas


def _get_api_key(config: Any) -> Optional[str]:
    """Retrieve API key from vault. None for local providers (Ollama)."""
    if config.llm_api_key_name:
        from clients.vault_client import get_api_key
        return get_api_key(config.llm_api_key_name)
    return None


def _serialize_response_content(response: Any) -> List[Dict[str, Any]]:
    """Convert LLM response content blocks to serializable dicts for message history."""
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


def _execute_tool_calls(
    tool_repo: 'ToolRepository',
    tool_calls: List[Dict[str, Any]],
    task_id: str,
) -> List[Dict[str, Any]]:
    """Execute tool calls via ToolRepository and return Anthropic-format tool results."""
    results = []
    for tc in tool_calls:
        tool_name = tc['tool_name']
        tool_input = tc['input']
        tool_use_id = tc['id']

        try:
            tool = tool_repo.get_tool(tool_name)
            result = tool.run(**tool_input)
            results.append({
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": json.dumps(result, default=str),
            })
        except Exception as e:
            logger.warning(f"Forage {task_id[:8]}: Tool {tool_name} failed: {e}")
            results.append({
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": json.dumps({"error": str(e)}),
                "is_error": True,
            })

    return results


def _parse_tool_result(content: str) -> Any:
    """Parse JSON tool result content back to a dict for trace readability."""
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return content


def _save_trace(trace_dir: Optional[str], task_id: str, trace: Dict[str, Any]) -> None:
    """Write trace to a JSON file in the user's forage data directory."""
    if not trace_dir:
        return
    try:
        from pathlib import Path
        path = Path(trace_dir) / f"{task_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(trace, f, indent=2, default=str)
        logger.debug(f"Forage {task_id[:8]}: Trace saved to {path}")
    except Exception as e:
        logger.warning(f"Forage {task_id[:8]}: Failed to save trace: {e}")


def _publish_result(
    event_bus: 'EventBus',
    continuum_id: str,
    task_id: str,
    status: str,
    data: Dict[str, Any],
) -> None:
    """Publish forage result to ForageTrinket via event bus."""
    from cns.core.events import UpdateTrinketEvent
    event_bus.publish(UpdateTrinketEvent.create(
        continuum_id=continuum_id,
        target_trinket='ForageTrinket',
        context={'task_id': task_id, 'status': status, **data},
    ))
