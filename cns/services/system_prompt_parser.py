"""
System prompt section parser for the user model pipeline.

Extracts section IDs and content from the system prompt XML structure.
Used by both assessment extraction and user model synthesis to establish
the canonical vocabulary of section IDs that flows end-to-end.
"""
import re
from dataclasses import dataclass
from typing import List

# Sections excluded from assessment (contain runtime data, not behavioral contract)
_BLOCKLISTED_SECTIONS = frozenset({"user", "environment"})


@dataclass(frozen=True)
class SystemPromptSection:
    """A parsed section from the system prompt."""
    section_id: str
    content: str


def _parse_system_prompt_sections(raw_prompt: str) -> List[SystemPromptSection]:
    """
    Extract top-level sections from the system prompt XML.

    Only returns sections that are direct children of the <mira:system_prompt>
    wrapper, not nested tags (e.g., <memory_refs> inside <output_directives>
    is excluded because it's nested).

    Args:
        raw_prompt: Raw system prompt text

    Returns:
        List of SystemPromptSection with section_id and content
    """
    # Match all tag pairs with their spans
    pattern = r'<(\w+)>(.*?)</\1>'
    all_matches = []

    for match in re.finditer(pattern, raw_prompt, re.DOTALL):
        section_id = match.group(1)
        if ':' in section_id:
            continue
        all_matches.append((section_id, match.group(2).strip(), match.start(), match.end()))

    # Filter to top-level only: exclude any match whose span falls inside another match
    sections = []
    for section_id, content, start, end in all_matches:
        is_nested = any(
            other_start < start and end < other_end
            for other_id, _, other_start, other_end in all_matches
            if other_id != section_id
        )
        if not is_nested:
            sections.append(SystemPromptSection(section_id=section_id, content=content))

    return sections


def _filter_sections(
    sections: List[SystemPromptSection],
    blocklist: frozenset = _BLOCKLISTED_SECTIONS
) -> List[SystemPromptSection]:
    """Remove blocklisted sections from a section list."""
    return [s for s in sections if s.section_id not in blocklist]


def anonymize_prompt(raw_prompt: str) -> str:
    """
    Remove user-identifying information from the system prompt.

    Used when passing the prompt to the assessor so it can evaluate behavior
    against the contract without user-specific details.

    Replacements:
        - {first_name} template var -> "The User"
        - {relative time since account creation} -> "a while"
        - <user>...</user> block -> removed entirely
    """
    result = raw_prompt

    # Replace template variables
    result = result.replace("{first_name}", "The User")
    result = result.replace("{relative time since account creation}", "a while")

    # Remove blocklisted sections entirely
    result = re.sub(r'<user>.*?</user>', '', result, flags=re.DOTALL)
    result = re.sub(r'<environment>.*?</environment>', '', result, flags=re.DOTALL)

    return result.strip()


def format_section_list(sections: List[SystemPromptSection]) -> str:
    """Format section IDs as a bullet list for prompt injection."""
    return "\n".join(f"- {s.section_id}" for s in sections)


def get_assessable_sections(raw_prompt: str) -> List[SystemPromptSection]:
    """
    Parse the system prompt and return only assessable (non-blocklisted) sections.

    Convenience function combining parse + filter.
    """
    return _filter_sections(_parse_system_prompt_sections(raw_prompt))
