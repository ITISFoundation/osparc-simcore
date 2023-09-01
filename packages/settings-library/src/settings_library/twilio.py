""" Account settings for twilio.com service

For twilio SMS services:
    SEE https://www.twilio.com/docs/sms/quickstart/python
    SEE https://support.twilio.com/hc/en-us/articles/223136027-Auth-Tokens-and-How-to-Change-Them
"""


import re
from re import Pattern

from pydantic import ConstrainedStr, Field, parse_obj_as

from .base import BaseCustomSettings


class CountryCodeStr(ConstrainedStr):
    # Based on https://countrycode.org/
    strip_whitespace: bool = True
    regex: Pattern[str] | None = re.compile(r"^\d{1,4}")

    class Config:
        frozen = True


class TwilioSettings(BaseCustomSettings):
    TWILIO_ACCOUNT_SID: str = Field(..., description="Twilio account String Identifier")
    TWILIO_AUTH_TOKEN: str = Field(..., description="API tokens")
    TWILIO_COUNTRY_CODES_W_ALPHANUMERIC_SID_SUPPORT: list[CountryCodeStr] = Field(
        default=parse_obj_as(
            list[CountryCodeStr],
            [
                "41",
            ],
        ),
        description="list of country-codes supporting/registered for alphanumeric sender ID"
        "See https://support.twilio.com/hc/en-us/articles/223133767-International-support-for-Alphanumeric-Sender-ID",
    )

    def is_alphanumeric_supported(self, phone_number: str) -> bool:
        # Some countries do not support alphanumeric serder ID
        #
        # SEE https://support.twilio.com/hc/en-us/articles/223181348-Alphanumeric-Sender-ID-for-Twilio-Programmable-SMS
        phone_number_wo_international_code = (
            phone_number.strip().removeprefix("00").lstrip("+")
        )
        return any(
            phone_number_wo_international_code.startswith(code)
            for code in self.TWILIO_COUNTRY_CODES_W_ALPHANUMERIC_SID_SUPPORT
        )
