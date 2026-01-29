from pydantic import Field

from ..api_schemas_webserver._base import OutputSchema


class EmailNotificationContentGet(OutputSchema):
    subject: str
    body_html: str
    body_text: str | None


class SMSNotificationContentGet(OutputSchema):
    text: str = Field(..., min_length=1)


type NotificationContentGet = EmailNotificationContentGet | SMSNotificationContentGet


class NotificationPreviewGet(OutputSchema):
    content: NotificationContentGet
