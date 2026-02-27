"""Terminal output rendering using prompt_toolkit's formatted text.

Uses print_formatted_text instead of Rich Console because Rich's ANSI output
is incompatible with prompt_toolkit's patch_stdout — the StdoutProxy captures
Rich's escape sequences as literal characters instead of passing them through.
print_formatted_text uses prompt_toolkit's native rendering and works correctly.
"""

from __future__ import annotations

from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import FormattedText

# prompt_toolkit ANSI style names: ansimagenta, ansibrightgreen, ansicyan, ansired, etc.


def print_user_message(text: str) -> None:
    """Print user message with magenta YOU: prefix."""
    _print_prefixed("YOU", "bold fg:ansimagenta", text)


def print_mira_response(text: str) -> None:
    """Print MIRA response with green MIRA: prefix."""
    _print_prefixed("MIRA", "bold fg:ansibrightgreen", text)


def print_thinking(text: str) -> None:
    """Print thinking tokens in dim italic — visually distinct from the response."""
    print_formatted_text(FormattedText([("italic fg:ansibrightblack", text)]))


def print_error(text: str) -> None:
    """Print error message in red."""
    print_formatted_text(FormattedText([("fg:ansired", text)]))


def print_tool_use(tool_name: str) -> None:
    """Print tool use indicator with cyan prefix."""
    _print_prefixed("TOOL", "bold fg:ansicyan", f"\u2699 {tool_name}")


def print_info(text: str) -> None:
    """Print informational message in dim style."""
    print_formatted_text(FormattedText([("fg:ansibrightblack", text)]))


def _print_prefixed(prefix: str, style: str, text: str) -> None:
    """Print a message with a styled prefix. No continuation indent."""
    lines = text.split("\n")

    parts: list[tuple[str, str]] = [(style, f"{prefix}: "), ("", lines[0])]
    for line in lines[1:]:
        parts.append(("", f"\n{line}"))

    print_formatted_text(FormattedText(parts))
