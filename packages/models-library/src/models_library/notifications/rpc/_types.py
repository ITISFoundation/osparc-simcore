from typing import Annotated

from pydantic import Field

from ._email import EmailAddressing, EmailMessage
from ._sms import SmsAddressing, SmsMessage

# NOTE: Addressing has no discriminator field of its own (e.g. SendMessageFromTemplateRequest
# resolves the channel from the template_ref instead), so it relies on structural validation.
type Addressing = EmailAddressing | SmsAddressing

type Message = Annotated[EmailMessage | SmsMessage, Field(discriminator="channel")]
