"""
Memory formatting utilities for consistent XML representation.

Provides standardized formatting of memory context (annotations, links) for:
- Batch processing prompts (consolidation)
- User-facing display (trinkets)

XML format matches the existing display patterns from proactive_memory_trinket.py.
"""
import logging
from typing import List

from lt_memory.models import Memory, AnnotationEntry
from utils.tag_parser import format_memory_id
from utils.timezone_utils import format_relative_time, parse_time_string

logger = logging.getLogger(__name__)


def format_annotations_xml(annotations: List[AnnotationEntry]) -> str:
    """
    Format annotations as XML for prompt inclusion.

    Follows the pattern from proactive_memory_trinket.py for consistency.

    Args:
        annotations: List of annotation dicts with 'text', 'created_at', 'source'

    Returns:
        XML string like:
        <annotations>
        <note added="2 days ago">Annotation text here</note>
        </annotations>

        Or "<annotations/>" if empty
    """
    if not annotations:
        return "<annotations/>"

    parts = ["<annotations>"]

    for ann in annotations:
        text = ann.get('text', '')
        created = ann.get('created_at', '')

        if created:
            try:
                ann_dt = parse_time_string(created)
                relative = format_relative_time(ann_dt)
                parts.append(f'<note added="{relative}">{text}</note>')
            except (ValueError, TypeError):
                # Fallback if timestamp parsing fails
                parts.append(f'<note>{text}</note>')
        else:
            parts.append(f'<note>{text}</note>')

    parts.append("</annotations>")
    return "\n".join(parts)


def format_links_summary_xml(
    memory: Memory,
    max_links: int = 3,
    include_text_preview: bool = True
) -> str:
    """
    Format memory links as XML summary for prompt inclusion.

    Shows link counts and optionally the top linked memories with previews.

    Args:
        memory: Memory object with inbound_links and outbound_links
        max_links: Maximum number of linked memories to show text for
        include_text_preview: Whether to include text preview of linked memories

    Returns:
        XML string like:
        <links inbound="3" outbound="1">
        <linked_memory id="mem_abc" link_type="supports" confidence="92">
        <text>Preview of linked memory text...</text>
        </linked_memory>
        </links>

        Or "<links inbound="0" outbound="0"/>" if no links
    """
    inbound = memory.inbound_links or []
    outbound = memory.outbound_links or []

    inbound_count = len(inbound)
    outbound_count = len(outbound)

    if inbound_count == 0 and outbound_count == 0:
        return '<links inbound="0" outbound="0"/>'

    parts = [f'<links inbound="{inbound_count}" outbound="{outbound_count}">']

    # Show top links (prefer outbound as they're the memory's assertions)
    links_to_show = []

    # Add outbound links first (what this memory links to)
    for link in outbound[:max_links]:
        links_to_show.append({
            'uuid': link.get('uuid', ''),
            'link_type': link.get('type', 'unknown'),
            'confidence': link.get('confidence'),
            'text': link.get('text', ''),  # May be populated by caller
            'direction': 'outbound'
        })

    # Fill remaining slots with inbound links
    remaining_slots = max_links - len(links_to_show)
    if remaining_slots > 0:
        for link in inbound[:remaining_slots]:
            links_to_show.append({
                'uuid': link.get('uuid', ''),
                'link_type': link.get('type', 'unknown'),
                'confidence': link.get('confidence'),
                'text': link.get('text', ''),
                'direction': 'inbound'
            })

    for link in links_to_show:
        raw_id = link['uuid']
        formatted_id = format_memory_id(raw_id) if raw_id else 'unknown'

        # Build attributes
        attrs = [f'id="{formatted_id}"', f'link_type="{link["link_type"]}"']

        confidence = link.get('confidence')
        if confidence is not None and confidence > 0.5:
            attrs.append(f'confidence="{int(confidence * 100)}"')

        parts.append(f"<linked_memory {' '.join(attrs)}>")

        # Include text preview if available and requested
        text = link.get('text', '')
        if include_text_preview and text:
            # Truncate long text
            preview = text[:100] + "..." if len(text) > 100 else text
            parts.append(f"<text>{preview}</text>")

        parts.append("</linked_memory>")

    parts.append("</links>")
    return "\n".join(parts)


def format_memories_for_consolidation(
    memories: List[Memory],
    include_annotations: bool = True,
    include_links: bool = True
) -> str:
    """
    Format multiple memories for consolidation prompt.

    Args:
        memories: List of Memory objects to format
        include_annotations: Whether to include annotations
        include_links: Whether to include links

    Returns:
        Formatted string with all memories and their context
    """
    formatted_memories = []

    for i, memory in enumerate(memories, 1):
        raw_id = str(memory.id) if memory.id else ''
        formatted_id = format_memory_id(raw_id) if raw_id else 'unknown'

        parts = [f"{formatted_id} — {memory.text}"]

        if include_annotations:
            parts.append(format_annotations_xml(memory.annotations))

        if include_links:
            parts.append(format_links_summary_xml(memory, max_links=2))

        formatted_memories.append("\n".join(parts))

    return "\n\n".join(formatted_memories)


