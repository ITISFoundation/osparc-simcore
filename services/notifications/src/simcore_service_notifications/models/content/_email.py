from typing import Self

from pydantic import model_validator

from ._content import Content


class EmailContent(Content):
    """Email notification content model."""

    subject: str
    body_html: str | None = None
    body_text: str | None = None

    @model_validator(mode="after")
    def _require_at_least_one_body_format(self) -> Self:
        if self.body_html is None and self.body_text is None:
            msg = "At least one of 'body_html' or 'body_text' is required"
            raise ValueError(msg)
        return self
