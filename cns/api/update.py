"""
Update Check API endpoint - version update notification.

Public endpoint that checks if a newer MIRA version is available.
Logs check requests with timestamp and IP to data/update_checks.log for analytics.
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import APIRouter, Request
from packaging import version as pkg_version
from pydantic import BaseModel, Field

from utils.timezone_utils import utc_now, format_utc_iso

logger = logging.getLogger(__name__)

# Dedicated file logger for update check analytics
_update_log_path = Path(__file__).parent.parent.parent / "data" / "update_checks.log"
_update_log_path.parent.mkdir(parents=True, exist_ok=True)

update_logger = logging.getLogger("update_checks")
update_logger.setLevel(logging.INFO)
# Rotate at 10MB, keep 5 backups
_handler = RotatingFileHandler(_update_log_path, maxBytes=10_000_000, backupCount=5)
_handler.setFormatter(logging.Formatter("%(asctime)s\t%(message)s"))
update_logger.addHandler(_handler)

router = APIRouter()


class UpdateCheckResponse(BaseModel):
    """Response for version update check."""
    update_available: bool
    latest_version: str | None = Field(default=None, description="Latest version if update available")
    checked_at: str = Field(..., description="ISO-8601 timestamp of check")


def get_latest_version() -> str:
    """Read latest version from VERSION file."""
    version_file = Path(__file__).parent.parent.parent / "VERSION"
    return version_file.read_text().strip()


def get_client_ip(request: Request) -> str:
    """Extract client IP, checking X-Forwarded-For for proxied requests."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For can be comma-separated list; first is original client
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/check_update", response_model=UpdateCheckResponse)
def check_update_endpoint(request: Request, version: str = "") -> UpdateCheckResponse:
    """
    Check if a newer MIRA version is available.

    Public endpoint - no authentication required.
    Logs: timestamp, client IP, version being checked.
    """
    latest = get_latest_version()
    client_ip = get_client_ip(request)

    # Log the update check for analytics (to data/update_checks.log)
    update_logger.info(f"ip={client_ip}\tversion={version or 'none'}\tlatest={latest}")

    # No version provided or invalid - can't compare
    if not version:
        return UpdateCheckResponse(
            update_available=False,
            latest_version=latest,
            checked_at=format_utc_iso(utc_now())
        )

    try:
        installed = pkg_version.parse(version)
        latest_parsed = pkg_version.parse(latest)

        if latest_parsed > installed:
            return UpdateCheckResponse(
                update_available=True,
                latest_version=latest,
                checked_at=format_utc_iso(utc_now())
            )
    except pkg_version.InvalidVersion as e:
        logger.warning(f"Invalid version format in update check: {version} - {e}")

    return UpdateCheckResponse(
        update_available=False,
        checked_at=format_utc_iso(utc_now())
    )
