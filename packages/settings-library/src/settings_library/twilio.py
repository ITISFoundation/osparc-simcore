""" Twilio settings

"""

from pydantic import Field

from .base import BaseCustomSettings


class TwilioSettings(BaseCustomSettings):
    # SEE https://www.twilio.com/docs/sms/quickstart/python
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str

    # SID stands for String Identifier: SMXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    # It’s a unique key that is used to identify specific resources. At Twilio, each SID has 34 digits
    # and you can identify the type of SID and the product it’s associated with
    # by the first two characters.
    TWILIO_MESSAGING_SID: str = Field(
        description="Corresponds to phone's String Identifier. from which SMS are sent (i.e. osparc side)",
        min_length=34,
        max_length=34,
    )
