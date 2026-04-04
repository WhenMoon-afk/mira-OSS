"""
IMAP Trigger -- Polls for new emails from configured senders.

Connects using the user's email_tool credentials. Dedup via Valkey
with 30-day TTL on Message-ID. Sanitizes content through
PromptInjectionDefense before building WorkItems.
"""
import email
import email.utils
import hashlib
import imaplib
import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from utils.timezone_utils import utc_now

from agents.sidebar import WorkItem

if TYPE_CHECKING:
    from agents.implementations.email_sidebar import EmailSidebarAgent

logger = logging.getLogger(__name__)

# Valkey key prefix for dedup. TTL = 30 days.
_DEDUP_PREFIX = "sidebar:processed:imap"
_DEDUP_TTL_SECONDS = 30 * 24 * 3600

# Truncate email body before injecting into agent context
_BODY_MAX_CHARS = 8000


class ImapTrigger:
    """Polls IMAP for new emails from watched sender addresses."""

    trigger_id = "imap_email"
    interface_name = "email_watcher"

    @property
    def agent_class(self) -> type:
        from agents.implementations.email_sidebar import EmailSidebarAgent
        return EmailSidebarAgent

    def __init__(self, watched_senders: list[str], max_age_hours: int = 24):
        self.watched_senders = [s.lower() for s in watched_senders]
        self.max_age_hours = max_age_hours
        # Maps item_id → email UID for IMAP flag setting in mark_processed
        self._uid_map: dict[str, int] = {}

    def check_for_new_items(self, user_id: str) -> list[WorkItem]:
        if not self.watched_senders:
            return []

        try:
            conn = self._connect(user_id)
        except (KeyError, ValueError, TypeError):
            # User has no email credentials configured — not an error
            return []
        except Exception as e:
            logger.error(f"IMAP connection failed for user {user_id}: {e}")
            return []

        items: list[WorkItem] = []
        try:
            conn.select("INBOX")
            for sender in self.watched_senders:
                items.extend(
                    self._check_sender(conn, sender, user_id)
                )
        except Exception as e:
            logger.error(f"IMAP search failed: {e}", exc_info=True)
        finally:
            try:
                conn.logout()
            except Exception:
                pass

        return items

    def mark_processed(self, user_id: str, item_id: str) -> None:
        valkey = self._get_valkey()
        key = f"{_DEDUP_PREFIX}:{user_id}:{item_id}"
        valkey.set(key, "1", ex=_DEDUP_TTL_SECONDS)

        # Set $MiraHandled IMAP flag for visibility in email clients
        uid = self._uid_map.pop(item_id, None)
        if uid:
            try:
                conn = self._connect(user_id)
                conn.select("INBOX")
                self._set_handled_flag(conn, uid)
                conn.logout()
            except Exception as e:
                logger.debug(f"Failed to set $MiraHandled on UID {uid}: {e}")

    def _check_sender(
        self,
        conn: imaplib.IMAP4_SSL,
        sender: str,
        user_id: str,
    ) -> list[WorkItem]:
        """Search for unprocessed emails from a single sender."""
        since_date = (utc_now() - timedelta(hours=self.max_age_hours)).strftime("%d-%b-%Y")
        criteria = f'FROM "{sender}" SINCE {since_date}'
        typ, data = conn.uid("SEARCH", None, criteria)
        if typ != "OK" or not data or not data[0]:
            return []

        uids = data[0].decode("utf-8").split()
        valkey = self._get_valkey()
        items: list[WorkItem] = []

        for uid_str in uids:
            uid = int(uid_str)
            msg_id = self._get_message_id(conn, uid)
            if not msg_id:
                continue

            # Dedup check
            dedup_key = f"{_DEDUP_PREFIX}:{user_id}:{msg_id}"
            if valkey.exists(dedup_key):
                continue

            # Fetch full message
            msg = self._fetch_message(conn, uid)
            if msg is None:
                continue

            # Verify sender matches watched address — some IMAP servers
            # don't reliably filter by FROM in SEARCH results
            _, from_addr = email.utils.parseaddr(msg.get("From", ""))
            if from_addr.lower() != sender:
                valkey.set(dedup_key, "skipped", ex=_DEDUP_TTL_SECONDS)
                continue

            # Build work item with sanitized content
            try:
                item = self._build_work_item(msg, uid, msg_id, conn)
                self._uid_map[msg_id] = uid
                items.append(item)
            except ValueError as e:
                # Injection defense rejected content
                logger.warning(
                    f"Email from {sender} rejected by injection defense: {e}"
                )
                # Mark as processed so we don't retry
                valkey.set(dedup_key, "rejected", ex=_DEDUP_TTL_SECONDS)

        return items

    def _build_work_item(
        self,
        msg: email.message.Message,
        uid: int,
        msg_id: str,
        conn: imaplib.IMAP4_SSL,
    ) -> WorkItem:
        """Extract email content, sanitize, and assemble into WorkItem.

        All attacker-controlled fields (subject, from, body) are run through
        injection defense as a single unit. ValueError propagates to caller
        for rejection + dedup marking.
        """
        from utils.prompt_injection_defense import (
            PromptInjectionDefense,
            TrustLevel,
        )

        raw_subject = msg.get("Subject", "(no subject)")
        raw_from = msg.get("From", "")
        date = msg.get("Date", "")
        raw_body = self._extract_body(msg)

        # Sanitize all attacker-controlled content as one unit
        full_content = (
            f"From: {raw_from}\n"
            f"Subject: {raw_subject}\n\n"
            f"{raw_body}"
        )

        defense = PromptInjectionDefense()
        sanitized, metadata = defense.sanitize_untrusted_content(
            content=full_content,
            source="email",
            trust_level=TrustLevel.UNTRUSTED,
            require_llm_detection=True,
        )

        # Truncate for agent context
        if len(sanitized) > _BODY_MAX_CHARS:
            sanitized = sanitized[:_BODY_MAX_CHARS] + "\n[truncated]"

        # Thread context from headers
        thread = self._assemble_thread_context(msg, raw_subject, raw_from, date)

        return WorkItem(
            item_id=msg_id,
            interface_name=self.interface_name,
            context={
                "sanitized_content": sanitized,
                "date": date,
                "thread": thread,
                "email_id": f"INBOX:{uid}",
                "injection_warnings": metadata.warnings or [],
            },
        )

    def _assemble_thread_context(
        self,
        msg: email.message.Message,
        subject: str,
        from_addr: str,
        date: str,
    ) -> list[dict]:
        """Build thread history from the current message."""
        return [{
            "from": from_addr,
            "subject": subject,
            "date": date,
            "message_id": msg.get("Message-ID", ""),
            "in_reply_to": msg.get("In-Reply-To", ""),
            "references": msg.get("References", ""),
        }]

    def _extract_body(self, msg: email.message.Message) -> str:
        """Extract plain text body from email message."""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        return payload.decode(charset, errors="replace")
            # Fallback to HTML if no plain text
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        return payload.decode(charset, errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        return ""

    def _get_message_id(
        self, conn: imaplib.IMAP4_SSL, uid: int
    ) -> str | None:
        """Fetch just the Message-ID header for a UID."""
        typ, data = conn.uid(
            "FETCH", str(uid), "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])"
        )
        if typ != "OK" or not data or not data[0]:
            return None
        header_data = data[0][1] if isinstance(data[0], tuple) else data[0]
        if isinstance(header_data, bytes):
            header_data = header_data.decode("utf-8", errors="replace")
        msg = email.message_from_string(header_data)
        return msg.get("Message-ID")

    def _fetch_message(
        self, conn: imaplib.IMAP4_SSL, uid: int
    ) -> email.message.Message | None:
        """Fetch full RFC822 message."""
        typ, data = conn.uid("FETCH", str(uid), "(RFC822)")
        if typ != "OK" or not data or not data[0]:
            return None
        raw = data[0][1] if isinstance(data[0], tuple) else data[0]
        if isinstance(raw, bytes):
            return email.message_from_bytes(raw)
        return email.message_from_string(raw)

    def _connect(self, user_id: str) -> imaplib.IMAP4_SSL:
        """Connect to IMAP using the user's per-user email_tool credentials."""
        import json
        from utils.user_credentials import UserCredentialService

        credential_service = UserCredentialService()
        config_json = credential_service.get_credential(
            credential_type="tool_config",
            service_name="email_tool",
        )
        creds = json.loads(config_json)

        conn = imaplib.IMAP4_SSL(
            creds["imap_server"],
            creds.get("imap_port", 993),
            timeout=30,
        )
        conn.login(creds["email_address"], creds["password"])
        return conn

    def _set_handled_flag(
        self, conn: imaplib.IMAP4_SSL, uid: int
    ) -> None:
        """Set $MiraHandled IMAP flag for visibility in email clients."""
        try:
            conn.uid("STORE", str(uid), "+FLAGS", "($MiraHandled)")
        except Exception as e:
            logger.debug(f"Failed to set $MiraHandled flag on UID {uid}: {e}")

    def _get_valkey(self):
        from clients.valkey_client import get_valkey_client
        return get_valkey_client()
