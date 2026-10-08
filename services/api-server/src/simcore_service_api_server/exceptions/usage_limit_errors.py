import math

from common_library.user_messages import user_message
from fastapi import status

from ._base import ApiServerBaseError


class ChatboxUsageBaseError(ApiServerBaseError):
    """Errors raised by the Chatbox usage limits enforcement layers.

    The error code (e.g. ``chatbox_window_quota_exceeded``) is part of the user message
    so that clients can branch on it without parsing prose.
    """

    msg_template = user_message("The Chatbox usage limit was exceeded.", _version=1)
    status_code = status.HTTP_403_FORBIDDEN

    code: str  # type: ignore[assignment] # required by mypy

    @property
    def retry_after_seconds(self) -> int | None:
        if (value := self.error_context().get("retry_after_seconds")) is None:
            return None
        return max(1, math.ceil(float(value)))

    @property
    def reset_at_iso8601(self) -> str | None:
        return self.error_context().get("reset_at_iso8601")


class ChatboxWindowQuotaExceededError(ChatboxUsageBaseError):
    code = "chatbox_window_quota_exceeded"
    msg_template = user_message(
        "chatbox_window_quota_exceeded: You have used your Chatbox allowance of {allowance_usd} "
        "for the current usage window. Your allowance will be available again at {reset_at}. "
        "If you need more allowance before then, please contact support.",
        _version=1,
    )
    status_code = status.HTTP_403_FORBIDDEN


class ProviderBudgetExhaustedError(ChatboxUsageBaseError):
    code = "provider_budget_exhausted"
    msg_template = user_message(
        "provider_budget_exhausted: The platform's AI provider budget has been exhausted. "
        "This is not caused by your usage. The Chatbox is unavailable for all users until the "
        "budget is topped up. Please contact support for more information.",
        _version=1,
    )
    status_code = status.HTTP_403_FORBIDDEN


class ChatboxRateLimitedError(ChatboxUsageBaseError):
    code = "chatbox_rate_limited"
    msg_template = user_message(
        "chatbox_rate_limited: You are sending Chatbox requests too quickly "
        "(limit {requests_per_minute} per minute). Please wait {retry_after_seconds} seconds and try again.",
        _version=1,
    )
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


class UsageLedgerUnavailableError(ChatboxUsageBaseError):
    # fail-closed for the spend layers (Window Quota, Global Budget Guard)
    code = "chatbox_usage_ledger_unavailable"
    msg_template = user_message(
        "chatbox_usage_ledger_unavailable: The Chatbox usage service is temporarily unavailable, "
        "so your request cannot be safely metered. Please try again shortly.",
        _version=1,
    )
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    @property
    def retry_after_seconds(self) -> int:
        return 5
