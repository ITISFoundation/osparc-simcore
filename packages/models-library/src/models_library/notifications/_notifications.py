from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic.config import JsonDict


class ChannelType(StrEnum):
    email = "email"


type TemplateName = Annotated[str, Field(min_length=1)]


class TemplateRef(BaseModel):
    channel: ChannelType
    template_name: TemplateName


class EmailContact(BaseModel):
    name: str
    email: EmailStr


class EmailMessageContent(BaseModel):
    subject: Annotated[str, Field(min_length=1, max_length=998)]
    body_html: str | None = None
    body_text: str | None = None


type NotificationsMessageContent = (
    EmailMessageContent
    # add here other channel contents (e.g. | SMSNotificationsContent)
)


class NotificationsMessage(BaseModel):
    channel: ChannelType


class EmailMessage(NotificationsMessage):
    channel: ChannelType = ChannelType.email
    from_: Annotated[EmailContact, Field(alias="from")]
    to: list[EmailContact]
    content: EmailMessageContent


class Template(BaseModel):
    ref: TemplateRef
    context_schema: Annotated[
        dict[str, Any],
        Field(
            description="JSON Schema defining the template's context variables",
        ),
    ]

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "ref": {"channel": "email", "template_name": "account_approved"},
                        "context_schema": {
                            "$defs": {
                                "User": {
                                    "properties": {
                                        "first_name": {
                                            "anyOf": [{"type": "string"}, {"type": "null"}],
                                            "default": None,
                                            "title": "First Name",
                                        }
                                    },
                                    "title": "User",
                                    "type": "object",
                                }
                            },
                            "properties": {
                                "user": {"$ref": "#/$defs/User"},
                                "link": {
                                    "format": "uri",
                                    "maxLength": 2083,
                                    "minLength": 1,
                                    "title": "Link",
                                    "type": "string",
                                },
                                "trial_account_days": {
                                    "anyOf": [{"type": "integer"}, {"type": "null"}],
                                    "default": None,
                                    "title": "Trial Account Days",
                                },
                                "extra_credits_in_usd": {
                                    "anyOf": [{"type": "integer"}, {"type": "null"}],
                                    "default": None,
                                    "title": "Extra Credits In Usd",
                                },
                            },
                            "required": ["user", "link"],
                            "title": "AccountApprovedTemplateContext",
                            "type": "object",
                        },
                    },
                ]
            }
        )

    model_config = ConfigDict(
        json_schema_extra=_update_json_schema_extra,
    )


class TemplatePreview(BaseModel):
    ref: TemplateRef
    message_content: dict[str, Any]

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "ref": {"channel": "email", "template_name": "account_approved"},
                        "message_content": {
                            "$subject": "Your account has been approved!",
                            "body_html": "<p>Dear User,</p><p>Your account has been approved.</p>",
                            "body_text": "Dear User,\n\nYour account has been approved.",
                        },
                    },
                ]
            }
        )
