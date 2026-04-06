"""
IMAP Trigger -- Polls for new emails matching per-user trigger rules.

Connects using the user's email_tool credentials. Rules are stored in
the user's SQLite DB (trigger_rules table) with trigger_id='imap_email'.
Each rule specifies a scope (IMAP folder), field (from/subject/body),
and regex pattern. Discovery only -- dedup handled by SidebarDispatcher
via sidebar_activity.
"""
import email
import email.utils
import imaplib
import logging
import re
from datetime import timedelta
from typing import Any

from utils.timezone_utils import utc_now

from agents.sidebar import WorkItem

logger = logging.getLogger(__name__)

# Valid field values for IMAP trigger rules
VALID_FIELDS = {"from", "subject", "body"}


class ImapTrigger:
    """Polls IMAP for new emails matching per-user trigger rules."""

    trigger_id = "imap_email"
    interface_name = "email_watcher"

    @property
    def agent_class(self) -> type:
        from agents.implementations.email_sidebar import EmailSidebarAgent
        return EmailSidebarAgent

    def __init__(self, max_age_hours: int = 24):
        self.max_age_hours = max_age_hours

    def check_for_new_items(self, user_id: str) -> list[WorkItem]:
        rules = self._load_rules(user_id)
        if not rules:
            logger.warning(
                f"IMAP trigger active for user {user_id} but no rules configured"
            )
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
            # Group rules by folder (scope)
            folders: dict[str, list[dict]] = {}
            for rule in rules:
                folders.setdefault(rule["scope"], []).append(rule)

            for folder, folder_rules in folders.items():
                items.extend(
                    self._check_folder(conn, folder, folder_rules)
                )
        except Exception as e:
            logger.error(f"IMAP search failed: {e}", exc_info=True)
        finally:
            try:
                conn.logout()
            except Exception:
                pass

        return items

    def on_dispatched(self, user_id: str, item_id: str) -> None:
        """Set $MiraHandled IMAP flag. Idempotent -- safe on retries."""
        folder, uid = self._parse_item_id(item_id)
        try:
            conn = self._connect(user_id)
            conn.select(folder)
            self._set_handled_flag(conn, uid)
            conn.logout()
        except Exception as e:
            logger.debug(
                f"Failed to set $MiraHandled on UID {uid}: {e}"
            )

    # ------------------------------------------------------------------
    # Conflict logging
    # ------------------------------------------------------------------

    def _write_conflict(self, item_id: str, description: str) -> None:
        """Write a conflict record to sidebar_activity for visibility."""
        try:
            from utils.userdata_manager import get_user_data_manager
            from utils.user_context import get_current_user_id
            from agents.base import ensure_activity_schema

            db = get_user_data_manager(get_current_user_id())
            ensure_activity_schema(db)
            db.execute(
                "INSERT INTO sidebar_activity "
                "(interface_name, thread_id, agent_id, summary, status, "
                "run_count, updated_at) "
                "VALUES (:interface_name, :thread_id, :agent_id, :summary, "
                ":status, :run_count, datetime('now')) "
                "ON CONFLICT(interface_name, thread_id) DO UPDATE SET "
                "summary = excluded.summary, status = excluded.status, "
                "updated_at = datetime('now')",
                {
                    'interface_name': self.interface_name,
                    'thread_id': item_id,
                    'agent_id': 'imap_email',
                    'summary': description,
                    'status': 'conflict',
                    'run_count': 0,
                },
            )
        except Exception as e:
            logger.error(f"Failed to write conflict record: {e}")

    # ------------------------------------------------------------------
    # Rule loading
    # ------------------------------------------------------------------

    def _load_rules(self, user_id: str) -> list[dict]:
        """Load enabled trigger rules for this trigger from the user's DB."""
        from uuid import UUID
        from utils.userdata_manager import get_user_data_manager

        db = get_user_data_manager(UUID(user_id))
        return db.select(
            "trigger_rules",
            where="trigger_id = :trigger_id AND enabled = 1",
            params={"trigger_id": self.trigger_id},
        )

    # ------------------------------------------------------------------
    # Per-folder polling
    # ------------------------------------------------------------------

    def _check_folder(
        self,
        conn: imaplib.IMAP4_SSL,
        folder: str,
        rules: list[dict],
    ) -> list[WorkItem]:
        """Fetch recent emails in a folder and apply rules."""
        try:
            typ, _ = conn.select(folder)
            if typ != "OK":
                logger.warning(f"Could not select folder {folder}")
                return []
        except imaplib.IMAP4.error as e:
            logger.warning(f"IMAP folder select failed for '{folder}': {e}")
            return []

        since_date = (
            utc_now() - timedelta(hours=self.max_age_hours)
        ).strftime("%d-%b-%Y")
        typ, data = conn.uid("SEARCH", None, f"SINCE {since_date}")
        if typ != "OK" or not data or not data[0]:
            return []

        uids = data[0].decode("utf-8").split()
        items: list[WorkItem] = []

        for uid_str in uids:
            uid = int(uid_str)
            item_id = f"{folder}:{uid}"

            msg = self._fetch_message(conn, uid)
            if msg is None:
                continue

            matched_rule, conflict = self._find_matching_rule(msg, rules)
            if conflict:
                self._write_conflict(item_id, conflict)
            elif matched_rule is not None:
                items.append(
                    self._build_work_item(msg, uid, item_id, folder, matched_rule)
                )

        return items

    # ------------------------------------------------------------------
    # Rule matching
    # ------------------------------------------------------------------

    def _find_matching_rule(
        self,
        msg: email.message.Message,
        rules: list[dict],
    ) -> tuple[dict | None, str | None]:
        """Return (matched_rule, None) or (None, conflict_description).

        Collects all rules that match the email. If multiple rules match
        with different prompts, the match is ambiguous — skip the email
        and return a conflict description for activity logging.
        Multiple matches with the same prompt (or no prompt) are fine.
        """
        cached_body: str | None = None
        matched: list[dict] = []

        for rule in rules:
            field = rule["field"]
            pattern = rule["pattern"]

            if field == "from":
                _, addr = email.utils.parseaddr(msg.get("From", ""))
                raw_from = msg.get("From", "")
                target = f"{raw_from}\n{addr}"
            elif field == "subject":
                target = msg.get("Subject", "")
            elif field == "body":
                if cached_body is None:
                    cached_body = self._extract_body(msg)
                target = cached_body
            else:
                continue

            try:
                if re.search(pattern, target, re.IGNORECASE):
                    matched.append(rule)
            except re.error as e:
                logger.warning(
                    f"Invalid regex in trigger rule {rule.get('id')}: "
                    f"{pattern!r} — {e}"
                )

        if not matched:
            return None, None

        if len(matched) == 1:
            return matched[0], None

        # Multiple matches — check for prompt conflict
        distinct_prompts = {r.get("prompt") or "" for r in matched}
        if len(distinct_prompts) <= 1:
            return matched[0], None

        rule_ids = [r.get("id") for r in matched]
        subject = msg.get("Subject", "(no subject)")
        conflict = (
            f"Email '{subject}' matched {len(matched)} rules with "
            f"conflicting prompts (rule IDs: {rule_ids}). "
            f"Fix rule overlap so match is unambiguous."
        )
        logger.warning(f"IMAP trigger: {conflict}")
        return None, conflict

    # ------------------------------------------------------------------
    # WorkItem construction
    # ------------------------------------------------------------------

    def _build_work_item(
        self,
        msg: email.message.Message,
        uid: int,
        item_id: str,
        folder: str,
        matched_rule: dict,
    ) -> WorkItem:
        """Extract email content and metadata into a WorkItem.

        Returns raw (unsanitized) content. Injection defense runs at the
        agent boundary (SidebarAgent.sanitize_untrusted_input) before the
        content enters any LLM context.
        """
        raw_subject = msg.get("Subject", "(no subject)")
        raw_from = msg.get("From", "")
        date = msg.get("Date", "")
        raw_body = self._extract_body(msg)

        full_content = (
            f"From: {raw_from}\n"
            f"Subject: {raw_subject}\n\n"
            f"{raw_body}"
        )

        thread = self._assemble_thread_context(msg, raw_subject, raw_from, date)

        context: dict[str, Any] = {
            "raw_content": full_content,
            "date": date,
            "thread": thread,
        }
        rule_prompt = matched_rule.get("prompt")
        if rule_prompt:
            context["agent_prompt"] = rule_prompt

        return WorkItem(
            item_id=item_id,
            interface_name=self.interface_name,
            context=context,
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

    # ------------------------------------------------------------------
    # Email body extraction
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # IMAP helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_item_id(item_id: str) -> tuple[str, int]:
        """Parse a folder:uid item_id back to (folder, uid)."""
        last_colon = item_id.rfind(":")
        return item_id[:last_colon], int(item_id[last_colon + 1:])

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

