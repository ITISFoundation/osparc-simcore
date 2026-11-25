import asyncio
from typing import Any

import twilio.rest  # type: ignore[import-untyped]
from settings_library.twilio import TwilioSettings


async def send_sms(
    account_settings: TwilioSettings,
    *,
    messaging_service_sid: str,
    to: str,
    body: str,
    sender: str | None = None,
) -> None:
    """Sends an sms via Twilio.

    TWILIO_BASE_URL replaces https://api.twilio.com as the root the message is posted to,
    which lets a local provider emulator stand in for the real service.

    NOTE: the Twilio SDK is synchronous, so the call is run in a thread executor.
    """
    client = twilio.rest.Client(
        account_settings.TWILIO_ACCOUNT_SID,
        account_settings.TWILIO_AUTH_TOKEN.get_secret_value(),
    )
    base_url = account_settings.TWILIO_BASE_URL
    if base_url is not None:
        # the SDK builds every Messages API url from this domain root when the request runs
        client.api.base_url = str(base_url)

    create_kwargs: dict[str, Any] = {
        "messaging_service_sid": messaging_service_sid,
        "to": to,
        "body": body,
    }
    if sender:
        create_kwargs["from_"] = sender

    def _create_message() -> None:
        # SEE https://www.twilio.com/docs/sms/quickstart/python
        client.messages.create(**create_kwargs)

    await asyncio.get_running_loop().run_in_executor(None, _create_message)
