"""Interactive settings UI with enter-to-toggle."""

from __future__ import annotations

import logging

from ui.terminal.config import TerminalConfig
from ui.terminal.renderer import print_error, print_mira_response

logger = logging.getLogger(__name__)


# Each setting: (config_key, display_label, type, [options for choice type])
SETTINGS_SPEC: list[tuple] = [
    ("show_thinking", "Show thinking tokens", "bool"),
    ("update_check", "Check for updates on startup", "bool"),
    ("mode", "Mode", "choice", ["local", "online"]),
    ("editor", "Editor", "str"),
    ("api_key", "API key (online mode)", "str"),
    ("api_url", "API URL override (empty = auto)", "str"),
]


def show_settings(config: TerminalConfig) -> None:
    """Display interactive settings. Enter number to toggle/edit, q to save."""
    while True:
        print()
        for i, spec in enumerate(SETTINGS_SPEC, 1):
            key, label, stype = spec[0], spec[1], spec[2]
            value = getattr(config, key)

            if stype == "bool":
                mark = "x" if value else " "
                print(f"  {i}. [{mark}] {label}")
            elif stype == "choice":
                print(f"  {i}. {label}: {value}")
            else:
                display = value if value else "(not set)"
                if key == "api_key" and value:
                    display = value[:8] + "..."
                print(f"  {i}. {label}: {display}")

        print()

        try:
            choice = input("Enter number to toggle/edit, q to save and exit: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if choice.lower() == "q":
            break

        try:
            idx = int(choice) - 1
            if not (0 <= idx < len(SETTINGS_SPEC)):
                print_error("Invalid number")
                continue

            spec = SETTINGS_SPEC[idx]
            key, stype = spec[0], spec[2]

            if stype == "bool":
                setattr(config, key, not getattr(config, key))
            elif stype == "choice":
                options = spec[3]
                current = getattr(config, key)
                next_idx = (options.index(current) + 1) % len(options)
                setattr(config, key, options[next_idx])
            else:
                try:
                    new_val = input(f"  New value for {spec[1]}: ").strip()
                    setattr(config, key, new_val)
                except (KeyboardInterrupt, EOFError):
                    pass

        except ValueError:
            print_error("Enter a number or 'q'")

    config.save()
    logger.info("Settings saved: mode=%s, thinking=%s", config.mode, config.show_thinking)
    print_mira_response("Settings saved")
