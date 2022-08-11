import asyncio
import logging
import os

from twilio.rest import Client

log = logging.getLogger(__name__)


async def send_sms_code(phone_number, code):
    def sender():
        log.info(
            "sending sms code to %s",
            f"{phone_number=}",
        )

        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        messaging_service_sid = os.environ.get("TWILIO_MESSAGING_SID")

        client = Client(account_sid, auth_token)
        message = client.messages.create(
            messaging_service_sid=messaging_service_sid,
            to=phone_number,
            body="Dear TI Planning Tool user, your verification code is {}".format(
                code
            ),
        )

        log.debug(
            "Got twilio client %s",
            f"{message=}",
        )

    await asyncio.get_event_loop().run_in_executor(None, sender)
