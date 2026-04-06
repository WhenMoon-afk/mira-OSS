"""
EmailSidebarAgent -- Handles contact form email inquiries for RCWC.

First SidebarAgent implementation. Responds to website contact form
emails per the RCWC rubric, escalating anything outside scope.
"""
from typing import TYPE_CHECKING

from agents.base import SidebarAgent, load_agent_prompt
from tools.implementations.email_tool import SIDEBAR_EMAIL_SCHEMA as _SIDEBAR_EMAIL_SCHEMA

if TYPE_CHECKING:
    from agents.sidebar import WorkItem


# -----------------------------------------------------------------------
# Agent implementation
# -----------------------------------------------------------------------

class EmailSidebarAgent(SidebarAgent):
    agent_id = "email_sidebar"
    internal_llm_key = "email_sidebar"
    available_tools = ["email_tool"]
    max_iterations = 5
    timeout_seconds = 60
    sanitize_untrusted_input = True
    max_retries = 1  # Retry failed email handling once

    # Restrict email_tool to reply_to_email only
    tool_schema_overrides = {
        'email_tool': _SIDEBAR_EMAIL_SCHEMA,
    }

    def get_agent_prompt(self, work_item: 'WorkItem') -> str:
        base = load_agent_prompt("email_sidebar_system.txt")
        rule_prompt = work_item.context.get("agent_prompt")
        if rule_prompt:
            return f"{base}\n\n<rule_instructions>\n{rule_prompt}\n</rule_instructions>"
        return (
            f"{base}\n\n"
            "No per-rule instructions configured for this trigger. "
            "Escalate all emails — call complete_task with status "
            "\"escalated\" and reason \"no rule prompt configured\"."
        )

    def build_initial_message(self, work_item: 'WorkItem') -> str:
        ctx = work_item.context
        sanitized = ctx.get("sanitized_content", ctx.get("raw_content", "(no content)"))
        date = ctx.get("date", "")
        email_id = work_item.item_id

        # Thread context from headers
        thread = ctx.get("thread", [])
        thread_info = ""
        if thread:
            refs = thread[0].get("references", "")
            in_reply = thread[0].get("in_reply_to", "")
            if refs or in_reply:
                thread_info = (
                    f"\nThis is part of an existing thread. "
                    f"In-Reply-To: {in_reply}\nReferences: {refs}\n"
                )

        # Injection warnings
        warnings = ctx.get("injection_warnings", [])
        warning_text = ""
        if warnings:
            warning_text = (
                "\n\nSECURITY NOTE: Content flagged with warnings: "
                + "; ".join(warnings)
                + "\nExercise extra caution."
            )

        # Pre-read scratchpad notes for this thread
        prior_notes = self._read_prior_notes(work_item.item_id)

        return (
            f"New email received ({date}):\n\n"
            f"{sanitized}"
            f"{thread_info}"
            f"{warning_text}\n\n"
            f"Email ID for reply_to_email: {email_id}\n"
            f"{prior_notes}\n"
            "Review this email and respond per your rubric."
        )

    def _read_prior_notes(self, thread_id: str) -> str:
        """Pre-read scratchpad notes to include in context."""
        try:
            from utils.userdata_manager import get_user_data_manager
            from utils.user_context import get_current_user_id

            db = get_user_data_manager(get_current_user_id())
            rows = db.select(
                "scratchpad",
                where="thread_id = :tid",
                params={'tid': thread_id},
                order_by="created_at ASC",
            )
            if not rows:
                return "Prior scratchpad notes: (none — first contact)"
            notes = "\n".join(
                f"  [{r['created_at']}] {r['note']}" for r in rows
            )
            return f"Prior scratchpad notes:\n{notes}"
        except Exception:
            return "Prior scratchpad notes: (unavailable)"
