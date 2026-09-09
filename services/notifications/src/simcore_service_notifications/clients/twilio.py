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

    NOTE: the Twilio SDK is synchronous, so the call is run in a thread executor.
    """
    client = twilio.rest.Client(account_settings.TWILIO_ACCOUNT_SID, account_settings.TWILIO_AUTH_TOKEN)

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

    await asyncio.get_event_loop().run_in_executor(None, _create_message)
