from ._email import EmailContact, EmailContent, EmailMessage

__all__: tuple[str, ...] = (
    "EmailContact",
    "EmailContent",
    "EmailMessage",
)

type Message = EmailMessage
