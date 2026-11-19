# pylint: disable=redefined-outer-name

from unittest.mock import MagicMock, patch

from pydantic import SecretStr
from settings_library.twilio import TwilioSettings
from simcore_service_notifications.clients.twilio import send_sms

_ACCOUNT_SETTINGS = TwilioSettings(
    TWILIO_ACCOUNT_SID="ACdummy",
    TWILIO_AUTH_TOKEN=SecretStr("plainDummyToken"),  # synthetic test fixture credential
    TWILIO_COUNTRY_CODES_W_ALPHANUMERIC_SID_SUPPORT=["41"],
)


async def test_send_sms_unwraps_credentials_before_calling_the_provider():
    with patch("twilio.rest.Client") as mock_client_cls:
        client = MagicMock()
        mock_client_cls.return_value = client

        await send_sms(
            _ACCOUNT_SETTINGS,
            messaging_service_sid="MGdummy",
            to="+41777777777",
            body="Your code is 123456",
            sender="osparc",
        )

    mock_client_cls.assert_called_once_with("ACdummy", "plainDummyToken")
    client.messages.create.assert_called_once_with(
        messaging_service_sid="MGdummy",
        to="+41777777777",
        body="Your code is 123456",
        from_="osparc",
    )


async def test_send_sms_omits_from_when_no_alphanumeric_sender():
    with patch("twilio.rest.Client") as mock_client_cls:
        client = MagicMock()
        mock_client_cls.return_value = client

        await send_sms(
            _ACCOUNT_SETTINGS,
            messaging_service_sid="MGdummy",
            to="+15551234567",
            body="Your code is 123456",
        )

    create_kwargs = client.messages.create.call_args.kwargs
    assert "from_" not in create_kwargs
    assert create_kwargs["to"] == "+15551234567"
