from ._content import Content


class EmailContent(Content):
    """Email notification content model."""

    subject: str
    body_html: str
    body_text: str
