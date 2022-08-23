""" Account settings for twilio.com service

For twilio SMS services:
    SEE https://www.twilio.com/docs/sms/quickstart/python
    SEE https://support.twilio.com/hc/en-us/articles/223136027-Auth-Tokens-and-How-to-Change-Them
"""


from pydantic import Field

from .base import BaseCustomSettings


class TwilioSettings(BaseCustomSettings):
    TWILIO_ACCOUNT_SID: str = Field(..., description="Twilio account String Identifier")
    TWILIO_AUTH_TOKEN: str = Field(..., description="API tokens")
