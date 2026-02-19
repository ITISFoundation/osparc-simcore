from ._email import EmailContact, EmailContent, EmailMessage, SingleEmailMessage

__all__: tuple[str, ...] = (
    "EmailContact",
    "EmailContent",
    "EmailMessage",
    "SingleEmailMessage",
)

type Message = EmailMessage
