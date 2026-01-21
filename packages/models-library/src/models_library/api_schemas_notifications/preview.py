from ..api_schemas_webserver._base import OutputSchema


class EmailNotificationContentGet(OutputSchema):
    subject: str
    body_html: str
    body_text: str | None


class SMSNotificationContentGet(OutputSchema):
    text: str


type NotificationContentGet = EmailNotificationContentGet | SMSNotificationContentGet


class NotificationPreviewGet(OutputSchema):
    content: NotificationContentGet
