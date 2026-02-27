"""MIRA Terminal Application.

Main entry point and chat loop using prompt_toolkit with:
- Dynamic prompt: separator line + "❯ " input, with status in bottom_toolbar
- Background API calls so the user can type while waiting for responses
- Custom Enter key binding that prevents submission during loading
- patch_stdout renders conversation content above the prompt block
"""

from __future__ import annotations

import argparse
import atexit
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

from prompt_toolkit import PromptSession
from prompt_toolkit.application import get_app
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style

from ui.terminal.api import MiraClient, TierInfo, check_for_update, strip_emotion_tag
from ui.terminal.commands import handle_command
from ui.terminal.config import CONFIG_FILE, UPDATE_CHECK_URL, TerminalConfig
from ui.terminal.renderer import (
    print_error,
    print_mira_response,
    print_thinking,
    print_tool_use,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
SERVER_STARTUP_TIMEOUT = 30

PROMPT_STYLE = Style.from_dict(
    {
        "separator": "fg:ansibrightblack",
        "prompt-char": "fg:ansicyan bold",
        "tier": "fg:ansimagenta",
        "domaindoc": "fg:ansibrightyellow bold",
        "loading": "fg:ansicyan",
        "update": "fg:ansiyellow bold",
        "bottom-toolbar": "noreverse",
    }
)

LOADING_FRAMES = ["[...]", "[.. ]", "[.  ]", "[   ]", "[.  ]", "[.. ]"]


class MiraTerminal:
    """Main terminal application managing the chat loop and UI state."""

    def __init__(self, config: TerminalConfig):
        self.config = config
        self.client: MiraClient | None = None

        # Loading state
        self.loading = False
        self._loading_frame = 0
        self._animation_thread: threading.Thread | None = None
        self._server_process: subprocess.Popen | None = None

        # Display state
        self.current_tier = ""
        self.current_tier_display = ""
        self.available_tiers: list[TierInfo] = []
        self.enabled_docs: list[str] = []
        self.update_version: str | None = None

        # prompt_toolkit
        self._kb = self._build_keybindings()
        self.session = PromptSession(key_bindings=self._kb)

    # ── Key Bindings ─────────────────────────────────────────────────────

    def _build_keybindings(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add("enter")
        def handle_enter(event):
            if self.loading:
                return  # Swallow Enter while waiting for response
            event.current_buffer.validate_and_handle()

        return kb

    # ── Dynamic Prompt ────────────────────────────────────────────────────

    def _get_prompt_message(self) -> FormattedText:
        """Dynamic prompt: separator line then input chevron.

        Layout (matching Claude Code):
          ──────────────────────────────────
          ❯ <user types here>
           Opus 4.6 | MyDomain              ← bottom_toolbar
        """
        import shutil

        width = shutil.get_terminal_size().columns
        return FormattedText([
            ("class:separator", "─" * width),
            ("", "\n"),
            ("class:prompt-char", "❯ "),
        ])

    def _get_bottom_toolbar(self) -> FormattedText:
        """Status bar below the input line: tier, domaindocs, loading, update."""
        parts: list[tuple[str, str]] = []

        if self.current_tier_display:
            parts.append(("class:tier", f" {self.current_tier_display}"))

        for doc in self.enabled_docs:
            parts.append(("", " | "))
            parts.append(("class:domaindoc", doc))

        if self.loading:
            parts.append(("", " "))
            parts.append(("class:loading", "waiting... "))
            parts.append(
                ("class:loading", LOADING_FRAMES[self._loading_frame % len(LOADING_FRAMES)])
            )

        if self.update_version:
            parts.append(("", " "))
            parts.append(("class:update", f"UPDATE: v{self.update_version}"))

        return FormattedText(parts)

    # ── Loading Animation ────────────────────────────────────────────────

    def _animate_loading(self) -> None:
        """Background thread: cycle loading animation by invalidating the toolbar."""
        while self.loading:
            self._loading_frame += 1
            try:
                get_app().invalidate()
            except Exception:
                pass
            time.sleep(0.3)

    def _start_loading(self) -> None:
        self.loading = True
        self._loading_frame = 0
        self._animation_thread = threading.Thread(
            target=self._animate_loading, daemon=True
        )
        self._animation_thread.start()

    def _stop_loading(self) -> None:
        self.loading = False
        if self._animation_thread:
            self._animation_thread.join(timeout=0.5)
            self._animation_thread = None
        try:
            get_app().invalidate()
        except Exception:
            pass

    # ── Background API Call ──────────────────────────────────────────────

    def _fetch_response(self, message: str) -> None:
        """Background thread: make API call and print response above the prompt.

        Uses try/finally to guarantee _stop_loading() runs — without this,
        any exception leaves the animation running and Enter permanently swallowed.
        """
        try:
            result = self.client.send_message(
                message, include_thinking=self.config.show_thinking
            )
        except Exception as e:
            result = {"success": False, "error": {"message": str(e)}}
        finally:
            self._stop_loading()

        if result.get("success"):
            data = result.get("data", {})

            # Thinking tokens
            thinking = data.get("thinking", "")
            if thinking and self.config.show_thinking:
                print_thinking(thinking)

            # Tool use indicators
            for tool in data.get("metadata", {}).get("tools_used", []):
                print_tool_use(tool)

            # Main response
            response = strip_emotion_tag(data.get("response", ""))
            print_mira_response(response)
        else:
            error = result.get("error", {}).get("message", "Unknown error")
            print_error(f"Error: {error}")

        print()  # Blank line after response

    # ── Server Management (Local Mode) ───────────────────────────────────

    def _is_server_running(self) -> bool:
        try:
            import requests

            response = requests.get(
                f"{self.config.get_api_url()}/v0/api/health", timeout=2
            )
            return response.status_code in (200, 503)
        except Exception:
            return False

    def _start_server(self) -> None:
        main_py = PROJECT_ROOT / "main.py"
        if not main_py.exists():
            raise RuntimeError(f"Cannot find main.py at {main_py}")
        self._server_process = subprocess.Popen(
            [sys.executable, str(main_py)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(PROJECT_ROOT),
        )
        atexit.register(self._stop_server)

    def _stop_server(self) -> None:
        if self._server_process is not None:
            logger.info("Stopping server (pid=%s)", self._server_process.pid)
            try:
                self._server_process.terminate()
                self._server_process.wait(timeout=5)
            except Exception:
                try:
                    self._server_process.kill()
                except Exception:
                    pass
            self._server_process = None

    def _wait_for_server(self, timeout: int = SERVER_STARTUP_TIMEOUT) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            if self._is_server_running():
                return True
            time.sleep(0.5)
        return False

    # ── State Helpers ────────────────────────────────────────────────────

    def _update_tier_display(self) -> None:
        """Sync tier display string from current_tier + available_tiers."""
        self.current_tier_display = next(
            (t.description for t in self.available_tiers if t.name == self.current_tier),
            self.current_tier,
        )

    # ── Startup ──────────────────────────────────────────────────────────

    def startup(self) -> None:
        """Initialize: server check, create client, load status, check updates."""
        # Local mode: ensure server is running
        if self.config.mode == "local" and not self._is_server_running():
            logger.info("Server not running, starting...")
            print("   [MIRA IS STARTING]   ", end="", flush=True)
            self._start_server()
            if not self._wait_for_server():
                print("\r" + " " * 40 + "\r", end="", flush=True)
                logger.error("Server failed to start within %ds", SERVER_STARTUP_TIMEOUT)
                print_error("Server failed to start")
                self._stop_server()
                sys.exit(1)
            # Overwrite the starting message
            print("\r" + " " * 40 + "\r", end="", flush=True)
            logger.info("Server started successfully")

        # Resolve token
        try:
            token = self.config.get_token()
        except Exception as e:
            logger.error("Token resolution failed: %s", e)
            print_error(f"Failed to get API token: {e}")
            sys.exit(1)

        self.client = MiraClient(self.config.get_api_url(), token)
        logger.info("Client initialized (mode=%s, url=%s)", self.config.mode, self.config.get_api_url())

        # Load display state
        self.current_tier, self.available_tiers = self.client.get_tier_info()
        self._update_tier_display()
        self.enabled_docs = self.client.get_enabled_domaindocs()

        # Update check (background — don't block startup for a network call)
        if self.config.update_check:
            threading.Thread(target=self._check_update, daemon=True).start()

    def _check_update(self) -> None:
        """Background thread: check for updates without blocking startup."""
        current_version = _get_version()
        available, version = check_for_update(current_version, UPDATE_CHECK_URL)
        if available:
            self.update_version = version
            try:
                get_app().invalidate()
            except Exception:
                pass

    # ── Main Loop ────────────────────────────────────────────────────────

    def run(self) -> None:
        """Interactive chat loop."""
        self.startup()

        # Push cursor near the bottom so the prompt block starts adjacent
        # to the terminal bottom. As conversation grows, content fills
        # upward naturally via patch_stdout.
        import shutil

        rows = shutil.get_terminal_size().lines
        print("\n" * max(0, rows - 4), end="", flush=True)

        with patch_stdout():
            while True:
                try:
                    user_input = self.session.prompt(
                        self._get_prompt_message,
                        style=PROMPT_STYLE,
                        bottom_toolbar=self._get_bottom_toolbar,
                        pre_run=lambda: get_app().__setattr__(
                            "erase_when_done", True
                        ),
                    ).strip()
                except (KeyboardInterrupt, EOFError):
                    print("\nGoodbye!")
                    break

                if not user_input:
                    continue

                if user_input.lower() in ("quit", "exit", "bye"):
                    print("Goodbye!")
                    break

                # Slash commands run synchronously between prompts
                if user_input.startswith("/"):
                    handle_command(user_input, self)
                    continue

                # Regular message: print it, then fire off background API call
                from ui.terminal.renderer import print_user_message

                print_user_message(user_input)
                print()

                self._start_loading()
                threading.Thread(
                    target=self._fetch_response, args=(user_input,), daemon=True
                ).start()

        # Cleanup
        if self._server_process:
            self._stop_server()


# ── Entry Points ─────────────────────────────────────────────────────────


def main() -> None:
    """CLI entry point with argparse."""
    parser = argparse.ArgumentParser(description="MIRA Terminal Client")
    parser.add_argument("--headless", type=str, help="One-shot message (non-interactive)")
    parser.add_argument(
        "--show-key", action="store_true", help="Display API key and exit"
    )
    args = parser.parse_args()

    # First-run setup if no config file exists
    if not TerminalConfig.exists():
        config = _first_run_setup()
    else:
        config = TerminalConfig.load()

    if args.show_key:
        _show_api_key(config)
        return

    if args.headless:
        _one_shot(config, args.headless)
        return

    terminal = MiraTerminal(config)
    terminal.run()


def _first_run_setup() -> TerminalConfig:
    """Interactive first-run setup. Prompts for mode and API key."""
    print("\nWelcome to MIRA Terminal.\n")
    print("  1. Local install (localhost:1993)")
    print("  2. Online (miraos.org)")
    print()

    try:
        choice = input("Select mode [1]: ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(0)

    config = TerminalConfig()

    if choice == "2":
        config.mode = "online"
        print()
        try:
            api_key = input("Enter your MIRA API key: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            sys.exit(0)
        if not api_key:
            print("No API key provided. Exiting.")
            sys.exit(1)
        config.api_key = api_key

    config.save()
    logger.info("First-run setup complete: mode=%s", config.mode)
    print(f"\nConfig saved to {CONFIG_FILE}\n")
    return config


def _show_api_key(config: TerminalConfig) -> None:
    """Display the API key and example curl command."""
    try:
        token = config.get_token()
        api_url = config.get_api_url()
        print(f"\nYour MIRA API Key: {token}\n")
        print("Use with curl:")
        print(f'  curl -H "Authorization: Bearer {token}" \\')
        print(f'       -H "Content-Type: application/json" \\')
        print(f"       -d '{{\"message\": \"Hello!\"}}' \\")
        print(f"       {api_url}/v0/api/chat\n")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _one_shot(config: TerminalConfig, message: str) -> None:
    """Send a single message and print the response."""
    try:
        token = config.get_token()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    client = MiraClient(config.get_api_url(), token)
    result = client.send_message(message, include_thinking=config.show_thinking)

    if result.get("success"):
        data = result.get("data", {})
        thinking = data.get("thinking", "")
        if thinking and config.show_thinking:
            # Dim italic via ANSI for headless mode (no Rich dependency needed)
            print(f"\033[2;3m{thinking}\033[0m")
        response = strip_emotion_tag(data.get("response", ""))
        print(response)
    else:
        print(
            f"Error: {result.get('error', {}).get('message', 'Unknown')}",
            file=sys.stderr,
        )
        sys.exit(1)


def _get_version() -> str:
    """Read current version from VERSION file."""
    version_file = PROJECT_ROOT / "VERSION"
    try:
        return version_file.read_text().strip()
    except Exception:
        return "unknown"
