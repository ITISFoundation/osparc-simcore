"""Celery worker task payloads for notifications service."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from ..api_schemas_notifications.message import EmailAddress, EmailContent


class SingleEmailMessage(BaseModel):
    """Payload for single email Celery task (one recipient per task)."""

    from_: Annotated[EmailAddress, Field(alias="from")]
    to: EmailAddress
    reply_to: EmailAddress | None = None

    content: EmailContent

    model_config = ConfigDict(
        validate_by_alias=True,
        validate_by_name=True,
    )
