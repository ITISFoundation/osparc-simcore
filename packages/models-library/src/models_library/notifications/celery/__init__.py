from ._email import EmailAttachment, EmailContact, EmailContent, EmailMessage

__all__: tuple[str, ...] = (
    "EmailAttachment",
    "EmailContact",
    "EmailContent",
    "EmailMessage",
)

type Message = EmailMessage
