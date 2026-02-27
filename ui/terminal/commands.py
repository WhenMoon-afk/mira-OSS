"""Slash command handling for the terminal UI."""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
import tempfile
from datetime import datetime
from typing import TYPE_CHECKING

from utils.timezone_utils import utc_now

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ui.terminal.app import MiraTerminal

from ui.terminal.renderer import print_error, print_mira_response


def handle_command(input_text: str, app: MiraTerminal) -> None:
    """Parse and dispatch a slash command."""
    parts = input_text[1:].split(maxsplit=1)
    cmd = parts[0].lower() if parts else ""
    arg = parts[1] if len(parts) > 1 else None

    handler = COMMANDS.get(cmd)
    if handler:
        logger.debug("Command: /%s %s", cmd, arg or "")
        handler(app, arg)
    else:
        print_error(f"Unknown command: /{cmd}")


# ── Command Handlers ─────────────────────────────────────────────────────


def cmd_help(app: MiraTerminal, arg: str | None) -> None:
    print_mira_response(
        "/tier [name] - view or change model tier\n"
        "/domaindoc - manage domain documents\n"
        "/collapse - end current conversation segment\n"
        "/status - system status\n"
        "/settings - configure preferences\n"
        "/clear - clear screen\n"
        "quit, exit, bye - exit"
    )


def cmd_status(app: MiraTerminal, arg: str | None) -> None:
    health = app.client.fetch_health()
    memory_count, has_more = app.client.fetch_memory_stats()
    user_info = app.client.fetch_user_info()
    segment_status = app.client.fetch_segment_status()

    app.current_tier, app.available_tiers = app.client.get_tier_info()
    app._update_tier_display()

    tier_desc = next(
        (t.description for t in app.available_tiers if t.name == app.current_tier),
        app.current_tier,
    )

    lines = []

    # System health
    health_data = health.get("data", {})
    system_status = health_data.get("status", "unknown")
    db_latency = (
        health_data.get("components", {}).get("database", {}).get("latency_ms")
    )
    latency_str = f" ({db_latency}ms)" if db_latency else ""
    lines.append(f"System      {system_status}{latency_str}")

    # Memories
    count_str = f"{memory_count}+" if has_more else str(memory_count)
    lines.append(f"Memories    {count_str} stored")

    # Segment
    if segment_status:
        if segment_status.get("has_active_segment"):
            collapse_at = segment_status.get("collapse_at")
            if collapse_at:
                remaining = _format_time_remaining(collapse_at)
                postponed = " (extended)" if segment_status.get("is_postponed") else ""
                lines.append(f"Segment     collapses in {remaining}{postponed}")
            else:
                lines.append("Segment     active")
        else:
            lines.append("Segment     collapsed")

    lines.append("")
    lines.append(f"Tier        {app.current_tier} ({tier_desc})")
    lines.append("")

    # User info
    if user_info:
        profile = user_info.get("profile", {})
        prefs = user_info.get("preferences", {})
        if profile.get("email"):
            lines.append(f"User        {profile['email']}")
        if prefs.get("timezone"):
            lines.append(f"Timezone    {prefs['timezone']}")

    print_mira_response("\n".join(lines))


def cmd_tier(app: MiraTerminal, arg: str | None) -> None:
    app.current_tier, app.available_tiers = app.client.get_tier_info()
    app._update_tier_display()
    tier_names = [t.name for t in app.available_tiers]

    if arg:
        arg_lower = arg.lower()
        resolved = (
            arg_lower
            if arg_lower in tier_names
            else next(
                (t.name for t in app.available_tiers if t.model == arg), None
            )
        )
        if resolved:
            if app.client.set_tier(resolved):
                app.current_tier = resolved
                app._update_tier_display()
                print_mira_response(f"Tier set to {resolved}")
            else:
                print_error("Failed to set tier")
        else:
            print_error(f"Unknown tier. Options: {', '.join(tier_names)}")
    else:
        current_model = next(
            (t.model for t in app.available_tiers if t.name == app.current_tier),
            app.current_tier,
        )
        lines = [f"Current: {app.current_tier} ({current_model})", ""]
        for t in app.available_tiers:
            marker = "\u2192" if t.name == app.current_tier else " "
            lines.append(f"  {marker} {t.name}: {t.model}")
        lines.append("")
        lines.append("Use /tier <name> to switch")
        print_mira_response("\n".join(lines))


def cmd_clear(app: MiraTerminal, arg: str | None) -> None:
    print("\033[2J\033[H", end="", flush=True)


def cmd_collapse(app: MiraTerminal, arg: str | None) -> None:
    resp = app.client.call_action("continuum", "collapse_segment")
    if resp.get("success"):
        print_mira_response(
            "The previous conversation segment has been collapsed. "
            "Feel free to continue in a new direction."
        )
    else:
        error_msg = resp.get("error", {}).get("message", "No active segment to collapse")
        print_error(f"Failed: {error_msg}")


def cmd_domaindoc(app: MiraTerminal, arg: str | None) -> None:
    if not arg:
        print_mira_response(
            "/domaindoc list\n"
            '/domaindoc create <label> "<description>"\n'
            "/domaindoc enable <label>\n"
            "/domaindoc disable <label>\n"
            "/domaindoc edit <label>"
        )
        return

    sub_parts = arg.split(maxsplit=1)
    sub_cmd = sub_parts[0].lower()
    sub_arg = sub_parts[1] if len(sub_parts) > 1 else None

    if sub_cmd == "list":
        _domaindoc_list(app)
    elif sub_cmd == "create" and sub_arg:
        _domaindoc_create(app, sub_arg)
    elif sub_cmd == "enable" and sub_arg:
        _domaindoc_toggle(app, sub_arg.strip(), enable=True)
    elif sub_cmd == "disable" and sub_arg:
        _domaindoc_toggle(app, sub_arg.strip(), enable=False)
    elif sub_cmd == "edit" and sub_arg:
        _domaindoc_edit(app, sub_arg.strip())
    else:
        print_error(f"Unknown domaindoc command. Try: /domaindoc list")


def cmd_settings(app: MiraTerminal, arg: str | None) -> None:
    from ui.terminal.config import CONFIG_FILE
    from ui.terminal.renderer import print_info
    from ui.terminal.settings import show_settings

    # Snapshot connection fields before settings UI
    old_mode = app.config.mode
    old_url = app.config.api_url
    old_key = app.config.api_key

    show_settings(app.config)

    # Check if connection-related fields changed
    if (app.config.mode != old_mode
            or app.config.api_url != old_url
            or app.config.api_key != old_key):
        print_info(
            f"Connection settings changed. Restart to apply, or edit {CONFIG_FILE} directly."
        )
    else:
        # Only refresh state if we're still on the same connection
        app.enabled_docs = app.client.get_enabled_domaindocs()


# ── Domaindoc Helpers ────────────────────────────────────────────────────


def _domaindoc_list(app: MiraTerminal) -> None:
    docs = app.client.list_domaindocs()
    if docs:
        lines = []
        for d in docs:
            status = "\u2713" if d.get("enabled") else "\u25cb"
            lines.append(f"{status} {d['label']}: {d.get('description', '')}")
        print_mira_response("\n".join(lines))
    else:
        print_mira_response(
            'No domaindocs found. Create one with /domaindoc create <label> "<description>"'
        )


def _domaindoc_create(app: MiraTerminal, raw_arg: str) -> None:
    try:
        create_parts = shlex.split(raw_arg)
        if len(create_parts) >= 2:
            label, description = create_parts[0], create_parts[1]
            resp = app.client.call_action(
                "domain_knowledge", "create", {"label": label, "description": description}
            )
            if resp.get("success"):
                print_mira_response(f"Created domaindoc '{label}'")
            else:
                print_error(
                    f"Error: {resp.get('error', {}).get('message', 'Unknown')}"
                )
        else:
            print_error('Usage: /domaindoc create <label> "<description>"')
    except ValueError as e:
        print_error(f"Parse error: {e}")


def _domaindoc_toggle(app: MiraTerminal, label: str, *, enable: bool) -> None:
    action = "enable" if enable else "disable"
    resp = app.client.call_action("domain_knowledge", action, {"label": label})
    if resp.get("success"):
        app.enabled_docs = app.client.get_enabled_domaindocs()
        print_mira_response(f"{'Enabled' if enable else 'Disabled'} '{label}'")
    else:
        print_error(f"Error: {resp.get('error', {}).get('message', 'Unknown')}")


def _domaindoc_edit(app: MiraTerminal, label: str) -> None:
    """Open domaindoc content in the user's configured editor."""
    logger.info("Editing domaindoc '%s' with %s", label, app.config.editor)
    doc = app.client.get_domaindoc(label)
    if doc is None:
        print_error(f"Domaindoc '{label}' not found")
        return

    content = doc.get("content", "")
    editor = app.config.editor

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, prefix=f"mira-{label}-"
    ) as f:
        f.write(content)
        tmppath = f.name

    try:
        result = subprocess.run([editor, tmppath])
        if result.returncode == 0:
            with open(tmppath) as f:
                new_content = f.read()
            if new_content != content:
                if app.client.update_domaindoc(label, new_content):
                    print_mira_response(f"Updated '{label}'")
                else:
                    print_error(f"Failed to save '{label}'")
            else:
                print_mira_response("No changes")
        else:
            print_error(f"Editor exited with code {result.returncode}")
    finally:
        os.unlink(tmppath)


# ── Utilities ────────────────────────────────────────────────────────────


def _format_time_remaining(collapse_at_iso: str) -> str:
    """Format time remaining until segment collapse."""
    try:
        collapse_at = datetime.fromisoformat(collapse_at_iso.replace("Z", "+00:00"))
        now = utc_now()
        total_seconds = int((collapse_at - now).total_seconds())
        if total_seconds <= 0:
            return "expired"
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
    except Exception:
        return "unknown"


COMMANDS: dict[str, callable] = {
    "help": cmd_help,
    "status": cmd_status,
    "tier": cmd_tier,
    "clear": cmd_clear,
    "collapse": cmd_collapse,
    "domaindoc": cmd_domaindoc,
    "settings": cmd_settings,
}
