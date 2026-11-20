from ._content import Content


class SmsContent(Content):
    """SMS notification content model."""

    body: str
