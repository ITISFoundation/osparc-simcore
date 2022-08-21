""" Twilio settings


 SID stands for String Identifier: SMXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
  It’s a unique key that is used to identify specific resources. At Twilio, each SID has 34 digits
  and you can identify the type of SID and the product it’s associated with
  by the first two characters.

SEE https://www.twilio.com/docs/sms/quickstart/python
"""


from .base import BaseCustomSettings


class TwilioSettings(BaseCustomSettings):
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
