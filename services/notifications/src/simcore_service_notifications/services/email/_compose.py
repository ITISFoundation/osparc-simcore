import mimetypes
from email.headerregistry import Address
from email.message import EmailMessage


def compose_email(
    from_: Address,
    to: Address,
    subject: str,
    content_text: str | None = None,
    content_html: str | None = None,
    reply_to: Address | None = None,
    bcc: list[Address] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> EmailMessage:
    """Compose an email message.

    Note:
        bcc param is a list and not set because email.headerregistry.Address is not hashable.
        Ensure unicity at a higher level, if needed.
    """
    msg = EmailMessage()
    msg["From"] = from_
    msg["To"] = to
    if reply_to:
        msg["Reply-To"] = reply_to
    if bcc:
        msg["Bcc"] = bcc

    msg["Subject"] = subject

    if extra_headers:
        for name, value in extra_headers.items():
            msg[name] = value

    if not content_text and not content_html:
        # NOTE: the RFC 5322 standard requires that the email message must have a content, either text or HTML.
        err_msg = "At least one of 'content_text' or 'content_html' is required"
        raise ValueError(err_msg)

    if content_text:
        msg.set_content(content_text)

    if content_html:
        msg.add_alternative(content_html, subtype="html")
    return msg


def _guess_file_type(file_name: str) -> tuple[str, str]:
    """
    Guess the MIME type based on the file name extension.
    """
    mimetype, _encoding = mimetypes.guess_type(file_name)
    if mimetype:
        maintype, subtype = mimetype.split("/", maxsplit=1)
    else:
        maintype, subtype = "application", "octet-stream"
    return maintype, subtype


def add_attachments(msg: EmailMessage, attachments: list[tuple[bytes, str]]):
    for file_data, file_name in attachments:
        # Use the filename to guess the file type
        maintype, subtype = _guess_file_type(file_name)

        # Add the attachment
        msg.add_attachment(
            file_data,
            filename=file_name,
            maintype=maintype,
            subtype=subtype,
        )
