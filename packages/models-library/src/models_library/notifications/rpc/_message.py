from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.config import JsonDict

from ...celery import GroupUUID, OwnerMetadata, TaskUUID
from ._template import TemplateRef


class SendMessageRequest(BaseModel):
    message: Annotated[
        dict[str, Any],
        Field(
            description="Channel-specific message payload. "
            "Structure depends on the channel type (e.g. EmailMessage for email).",
        ),
    ]
    owner_metadata: OwnerMetadata | None = None

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "message": {
                            "channel": "email",
                            "from": {
                                "name": "osparc support",
                                "email": "support@osparc.io",
                            },
                            "to": [
                                {
                                    "name": "John Doe",
                                    "email": "john@example.com",
                                }
                            ],
                            "content": {
                                "subject": "Welcome!",
                                "body_html": "<p>Welcome to osparc!</p>",
                                "body_text": "Welcome to osparc!",
                            },
                        },
                        "owner_metadata": {
                            "user_id": 123,
                            "product_name": "osparc",
                            "owner": "notification-service",
                        },
                    },
                ]
            }
        )

    model_config = ConfigDict(frozen=True, json_schema_extra=_update_json_schema_extra)


class SendMessageFromTemplateRequest(BaseModel):
    envelope: Annotated[
        dict[str, Any],
        Field(
            description="Channel-specific envelope (addressing info). "
            "Structure depends on the channel type (e.g. from/to for email). "
            "Does NOT include message content, which is generated from the template.",
        ),
    ]

    # fields used to generate the message content
    template_ref: TemplateRef
    context: Annotated[
        dict[str, Any],
        Field(
            description="Template context variables. Must conform to the context_schema of the referenced template.",
        ),
    ]
    owner_metadata: OwnerMetadata | None = None

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "envelope": {
                            "channel": "email",
                            "from": {
                                "name": "osparc support",
                                "email": "support@osparc.io",
                            },
                            "to": [
                                {
                                    "name": "John Doe",
                                    "email": "john@example.com",
                                }
                            ],
                        },
                        "template_ref": {
                            "channel": "email",
                            "template_name": "account_approved",
                        },
                        "context": {
                            "user": {"first_name": "John"},
                            "link": "https://osparc.io",
                        },
                        "owner_metadata": {
                            "user_id": 123,
                            "product_name": "osparc",
                            "owner": "notification-service",
                        },
                    },
                ]
            }
        )

    model_config = ConfigDict(frozen=True, json_schema_extra=_update_json_schema_extra)


class SendMessageResponse(BaseModel):
    task_or_group_uuid: TaskUUID | GroupUUID
    task_name: str

    model_config = ConfigDict(frozen=True)
