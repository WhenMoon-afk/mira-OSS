"""Terminal client configuration with JSON persistence."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".mira"
CONFIG_FILE = CONFIG_DIR / "terminal.json"

ONLINE_API_URL = "https://miraos.org"
LOCAL_API_URL = "http://localhost:1993"
UPDATE_CHECK_URL = "https://miraos.org/check_update"


class TerminalConfig(BaseModel):
    """User preferences for the MIRA terminal client."""

    mode: str = Field(default="local", description="'online' or 'local'")
    api_url: str = Field(default="", description="Override API URL (empty = auto from mode)")
    api_key: str = Field(default="", description="API key for online mode")
    show_thinking: bool = Field(default=False, description="Display thinking tokens")
    editor: str = Field(default="nano", description="Editor for domaindoc editing")
    update_check: bool = Field(default=True, description="Check for updates on startup")

    def get_api_url(self) -> str:
        """Resolve effective API URL based on mode."""
        if self.api_url:
            return self.api_url
        return LOCAL_API_URL if self.mode == "local" else ONLINE_API_URL

    def get_token(self) -> str:
        """Resolve API token based on mode.

        Local mode: auto-generated key from Vault.
        Online mode: user-provided API key from config.
        """
        if self.mode == "online":
            if not self.api_key:
                raise ValueError(
                    "Online mode requires an API key. Use /settings to configure."
                )
            return self.api_key
        from clients.vault_client import get_api_key

        return get_api_key("mira_api")

    def save(self) -> None:
        """Write config to ~/.mira/terminal.json."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(self.model_dump(), indent=2))
        logger.debug("Config saved to %s", CONFIG_FILE)

    @classmethod
    def load(cls) -> TerminalConfig:
        """Load config from disk, or return defaults if missing/corrupt."""
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text())
                logger.debug("Config loaded from %s", CONFIG_FILE)
                return cls(**data)
            except Exception as e:
                logger.warning("Config file corrupt, using defaults: %s", e)
        return cls()

    @classmethod
    def exists(cls) -> bool:
        """Check if a config file has been created."""
        return CONFIG_FILE.exists()
