# pylint: disable=redefined-outer-name

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, ClassVar, Final
from unittest.mock import MagicMock, patch

import pytest
from pydantic import AnyHttpUrl, SecretStr, TypeAdapter
from settings_library.twilio import TwilioSettings
from simcore_service_notifications.clients.twilio import send_sms

_ACCOUNT_SETTINGS: Final[TwilioSettings] = TwilioSettings(
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


_REPLY_BODY: Final[dict[str, Any]] = {"sid": "SMfakeSid", "status": "queued"}
_JOIN_TIMEOUT_S: Final[float] = 5.0


class _TwilioMessagesApiHandler(BaseHTTPRequestHandler):
    """Records the requests sent to it and replies like the Twilio Messages API"""

    received: ClassVar[list[dict[str, str]]] = []

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode()
        _TwilioMessagesApiHandler.received.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization", ""),
                "body": body,
            }
        )
        payload = json.dumps(_REPLY_BODY).encode()
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture
def twilio_messages_api() -> Iterator[tuple[AnyHttpUrl, list[dict[str, str]]]]:
    """Local stand-in for the Twilio Messages API, with the requests it received"""
    server = HTTPServer(("127.0.0.1", 0), _TwilioMessagesApiHandler)
    _TwilioMessagesApiHandler.received.clear()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = TypeAdapter(AnyHttpUrl).validate_python(f"http://127.0.0.1:{server.server_address[1]}")
        yield endpoint, _TwilioMessagesApiHandler.received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=_JOIN_TIMEOUT_S)


async def test_send_sms_posts_to_the_configured_base_url(twilio_messages_api: tuple[AnyHttpUrl, list[dict[str, str]]]):
    """TWILIO_BASE_URL replaces api.twilio.com as the place the message is posted to"""
    base_url, received = twilio_messages_api
    account_settings = _ACCOUNT_SETTINGS.model_copy(update={"TWILIO_BASE_URL": base_url})

    await send_sms(
        account_settings,
        messaging_service_sid="MGdummy",
        to="+41777777777",
        body="Your code is 123456",
        sender="osparc",
    )

    assert len(received) == 1
    request = received[0]
    assert request["path"] == "/2010-04-01/Accounts/ACdummy/Messages.json"
    assert request["authorization"].startswith("Basic ")
    assert "To=%2B41777777777" in request["body"]
    assert "From=osparc" in request["body"]
    assert "MessagingServiceSid=MGdummy" in request["body"]
