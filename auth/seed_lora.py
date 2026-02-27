"""
Seed feedback tracking for new users.

Initializes the feedback_synthesis_tracking table during account creation.
The user model pipeline will populate it with observations over time.
"""

import logging

from cns.infrastructure.feedback_tracker import FeedbackTracker

logger = logging.getLogger(__name__)


def seed_lora_postgres(user_id: str) -> None:
    """
    Initialize feedback tracking in PostgreSQL for a new user.

    Creates a feedback_synthesis_tracking row with defaults.
    The user model will be populated by the assessment/synthesis pipeline
    after sufficient use-days.

    Args:
        user_id: UUID of the user (as string)

    Raises:
        RuntimeError: If database initialization fails
    """
    try:
        tracker = FeedbackTracker()
        tracker.initialize_user(user_id)
        logger.debug("Initialized feedback tracking")

    except Exception as e:
        logger.error("Failed to initialize feedback tracking: %s", e, exc_info=True)
        raise RuntimeError(f"Feedback tracking initialization failed: {e}")
