""" Account settings for twilio.com service

For twilio SMS services:
    SEE https://www.twilio.com/docs/sms/quickstart/python
    SEE https://support.twilio.com/hc/en-us/articles/223136027-Auth-Tokens-and-How-to-Change-Them
"""

from typing import Annotated, TypeAlias

from pydantic import BeforeValidator, Field, StringConstraints, TypeAdapter

from .base import BaseCustomSettings

CountryCodeStr: TypeAlias = Annotated[
    str,
    BeforeValidator(str),
    # Based on https://countrycode.org/
    StringConstraints(strip_whitespace=True, pattern=r"^\d{1,4}"),
]


class TwilioSettings(BaseCustomSettings):
    TWILIO_ACCOUNT_SID: Annotated[
        str,
        Field(description="Twilio account String Identifier"),
    ]

    TWILIO_AUTH_TOKEN: Annotated[
        str,
        Field(description="API tokens"),
    ]

    TWILIO_COUNTRY_CODES_W_ALPHANUMERIC_SID_SUPPORT: Annotated[
        list[CountryCodeStr],
        Field(
            description="list of country-codes supporting/registered for alphanumeric sender ID"
            "See https://support.twilio.com/hc/en-us/articles/223133767-International-support-for-Alphanumeric-Sender-ID",
        ),
    ] = TypeAdapter(list[CountryCodeStr]).validate_python(
        [
            "41",
        ],
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
            for code in self.TWILIO_COUNTRY_CODES_W_ALPHANUMERIC_SID_SUPPORT  # pylint:disable=not-an-iterable
        )
