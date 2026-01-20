from pydantic import BaseModel


class NotificationMessage(BaseModel):
    subject: str | None
    body_html: str | None
    body_text: str | None
