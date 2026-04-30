from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.config import JsonDict

from ...celery import TaskID
from ._email import Addressing, Message
from ._template import TemplateRef


class SendMessageRequest(BaseModel):
    message: Annotated[
        Message,
        Field(
            description="Channel-specific message payload (e.g. EmailMessage for email).",
        ),
    ]
    owner: str | None = None
    user_id: int | None = None
    product_name: str | None = None

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "message": {
                            "channel": "email",
                            "addressing": {
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
                            "content": {
                                "subject": "Welcome!",
                                "body_html": "<p>Welcome to osparc!</p>",
                                "body_text": "Welcome to osparc!",
                            },
                        },
                        "owner": "notification-service",
                        "user_id": 123,
                        "product_name": "osparc",
                    },
                ]
            }
        )

    model_config = ConfigDict(frozen=True, json_schema_extra=_update_json_schema_extra)


class SendMessageFromTemplateRequest(BaseModel):
    addressing: Annotated[
        Addressing,
        Field(
            description="Channel-specific addressing info. "
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
    owner: str | None = None
    user_id: int | None = None
    product_name: str | None = None

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "addressing": {
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
                        "owner": "notification-service",
                        "user_id": 123,
                        "product_name": "osparc",
                    },
                ]
            }
        )

    model_config = ConfigDict(frozen=True, json_schema_extra=_update_json_schema_extra)


class SendMessageResponse(BaseModel):
    task_id: TaskID
    task_name: str

    model_config = ConfigDict(frozen=True)
