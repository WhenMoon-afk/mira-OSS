"""MIRA API client for the terminal UI."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 120
ACTION_TIMEOUT = 10


@dataclass
class TierInfo:
    """LLM tier information from the API."""

    name: str
    model: str
    description: str


class MiraClient:
    """HTTP client for the MIRA API."""

    def __init__(self, api_url: str, token: str):
        self.api_url = api_url.rstrip("/")
        self.token = token
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # ── Chat ─────────────────────────────────────────────────────────────

    def send_message(self, message: str, include_thinking: bool = False) -> dict:
        """Send a chat message. Returns raw API response dict."""
        url = f"{self.api_url}/v0/api/chat"
        payload: dict = {"message": message}
        if include_thinking:
            payload["include_thinking"] = True
        try:
            response = requests.post(
                url, headers=self._headers, json=payload, timeout=REQUEST_TIMEOUT
            )
            return response.json()
        except requests.exceptions.Timeout:
            logger.warning("Chat request timed out after %ds", REQUEST_TIMEOUT)
            return {"success": False, "error": {"message": "Request timed out"}}
        except requests.exceptions.ConnectionError:
            logger.warning("Cannot connect to %s", self.api_url)
            return {
                "success": False,
                "error": {"message": f"Cannot connect to {self.api_url}"},
            }
        except Exception as e:
            logger.error("Chat request failed: %s", e)
            return {"success": False, "error": {"message": str(e)}}

    # ── Actions ──────────────────────────────────────────────────────────

    def call_action(self, domain: str, action: str, data: dict | None = None) -> dict:
        """Call the actions API. Returns raw API response dict."""
        url = f"{self.api_url}/v0/api/actions"
        try:
            response = requests.post(
                url,
                headers=self._headers,
                json={"domain": domain, "action": action, "data": data or {}},
                timeout=ACTION_TIMEOUT,
            )
            return response.json()
        except Exception as e:
            logger.error("Action %s/%s failed: %s", domain, action, e)
            return {"success": False, "error": {"message": str(e)}}

    # ── Data Fetching ────────────────────────────────────────────────────

    def fetch_history(self, limit: int = 20) -> list[dict]:
        """Fetch recent message history."""
        url = f"{self.api_url}/v0/api/data"
        try:
            response = requests.get(
                url,
                headers=self._headers,
                params={"type": "history", "limit": limit},
                timeout=10,
            )
            result = response.json()
            if result.get("success"):
                return result.get("data", {}).get("messages", [])
        except Exception:
            pass
        return []

    def fetch_health(self) -> dict:
        """Fetch system health."""
        url = f"{self.api_url}/v0/api/health"
        try:
            response = requests.get(
                url, headers={"Authorization": f"Bearer {self.token}"}, timeout=5
            )
            return response.json()
        except Exception:
            return {"data": {"status": "unknown"}}

    def fetch_memory_stats(self) -> tuple[int, bool]:
        """Fetch memory count. Returns (count, has_more)."""
        url = f"{self.api_url}/v0/api/data"
        try:
            response = requests.get(
                url,
                headers=self._headers,
                params={"type": "memories", "limit": 100},
                timeout=5,
            )
            result = response.json()
            if result.get("success"):
                meta = result.get("data", {}).get("meta", {})
                return meta.get("total_returned", 0), meta.get("has_more", False)
        except Exception:
            pass
        return 0, False

    def fetch_user_info(self) -> dict | None:
        """Fetch user profile info."""
        url = f"{self.api_url}/v0/api/data"
        try:
            response = requests.get(
                url,
                headers=self._headers,
                params={"type": "user"},
                timeout=5,
            )
            result = response.json()
            if result.get("success"):
                return result.get("data", {})
        except Exception:
            pass
        return None

    def fetch_segment_status(self) -> dict | None:
        """Fetch segment timeout status."""
        resp = self.call_action("continuum", "get_segment_status")
        if resp.get("success"):
            return resp.get("data", {})
        return None

    # ── Tier Management ──────────────────────────────────────────────────

    def get_tier_info(self) -> tuple[str, list[TierInfo]]:
        """Get current tier and available tiers."""
        resp = self.call_action("continuum", "get_llm_tier")
        if resp.get("success"):
            data = resp.get("data", {})
            current = data.get("tier", "gemini-low")
            tiers = [
                TierInfo(
                    name=t["name"],
                    model=t.get("model", t.get("description", t["name"])),
                    description=t.get("description", t["name"]),
                )
                for t in data.get("available_tiers", [])
            ]
            return current, tiers
        return "gemini-low", []

    def set_tier(self, tier: str) -> bool:
        """Set LLM tier preference."""
        resp = self.call_action("continuum", "set_llm_tier", {"tier": tier})
        return resp.get("success", False)

    # ── Domain Knowledge ─────────────────────────────────────────────────

    def get_enabled_domaindocs(self) -> list[str]:
        """Get labels of enabled domaindocs."""
        resp = self.call_action("domain_knowledge", "list")
        if resp.get("success"):
            data = resp.get("data", {})
            return [d["label"] for d in data.get("domaindocs", []) if d.get("enabled")]
        return []

    def list_domaindocs(self) -> list[dict]:
        """Get all domaindocs with metadata."""
        resp = self.call_action("domain_knowledge", "list")
        if resp.get("success"):
            return resp.get("data", {}).get("domaindocs", [])
        return []

    def get_domaindoc(self, label: str) -> dict | None:
        """Get a single domaindoc's full content."""
        resp = self.call_action("domain_knowledge", "get", {"label": label})
        if resp.get("success"):
            return resp.get("data", {})
        return None

    def update_domaindoc(self, label: str, content: str) -> bool:
        """Update a domaindoc's content."""
        resp = self.call_action(
            "domain_knowledge", "update", {"label": label, "content": content}
        )
        return resp.get("success", False)

    # ── Server Health ────────────────────────────────────────────────────

    def is_healthy(self) -> bool:
        """Quick connectivity check."""
        try:
            response = requests.get(
                f"{self.api_url}/v0/api/health", timeout=2
            )
            return response.status_code in (200, 503)
        except Exception:
            return False


# ── Standalone Utilities ─────────────────────────────────────────────────


def check_for_update(current_version: str, update_url: str) -> tuple[bool, str | None]:
    """Check miraos.org for available updates.

    Returns (update_available, latest_version). Silent on failure.
    """
    if current_version == "unknown":
        return False, None
    try:
        response = requests.get(
            update_url, params={"version": current_version}, timeout=3
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("update_available"):
                return True, data.get("latest_version")
    except Exception as e:
        logger.debug("Update check failed: %s", e)
    return False, None


def strip_emotion_tag(text: str) -> str:
    """Remove <mira:my_emotion> tags from response text."""
    return re.sub(
        r"\n?<mira:my_emotion>.*?</mira:my_emotion>", "", text, flags=re.DOTALL
    ).strip()
