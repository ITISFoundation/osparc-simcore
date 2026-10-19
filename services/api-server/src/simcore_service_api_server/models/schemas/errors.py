from typing import Any

from common_library.error_codes import ErrorCodeStr
from pydantic import BaseModel, ConfigDict, Field


class ErrorGet(BaseModel):
    # We intentionally keep it open until more restrictive policy is implemented
    # Check use cases:
    #   - https://github.com/ITISFoundation/osparc-issues/issues/958
    #   - https://github.com/ITISFoundation/osparc-simcore/issues/2520
    #   - https://github.com/ITISFoundation/osparc-simcore/issues/2446
    errors: list[Any]
    support_id: ErrorCodeStr | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "errors": [
                    "some error message",
                    "another error message",
                ]
            }
        }
    )


class UsageLimitErrorGet(ErrorGet):
    """ErrorGet with structured fields for Chatbox usage-limit rejections.

    Clients can branch on ``code`` and surface ``retry_after_seconds``/``reset_at``
    without parsing the prose in ``errors``.
    """

    code: str = Field(
        ...,
        description="Stable machine-readable code identifying the usage-limit rejection",
    )
    retry_after_seconds: int | None = Field(
        None,
        description="Seconds to wait before the request can be retried, when known",
    )
    reset_at: str | None = Field(
        None,
        description="ISO-8601 UTC instant when the allowance becomes available again (usage window quota), when known",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "errors": ["chatbox_window_quota_exceeded: You have used your Chatbox allowance ..."],
                "support_id": None,
                "code": "chatbox_window_quota_exceeded",
                "retry_after_seconds": 1800,
                "reset_at": "2026-01-01T12:00:00+00:00",
            }
        }
    )
