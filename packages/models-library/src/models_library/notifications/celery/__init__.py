from ._email import EmailContact, EmailContent, EmailEnvelope, EmailMessage

__all__: tuple[str, ...] = (
    "EmailContact",
    "EmailContent",
    "EmailEnvelope",
    "EmailMessage",
)

type Message = EmailMessage
