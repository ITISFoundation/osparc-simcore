from typing import Annotated

from pydantic import Field

from ._email import EmailMessage
from ._sms import SmsMessage

type Message = Annotated[EmailMessage | SmsMessage, Field(discriminator="channel")]
