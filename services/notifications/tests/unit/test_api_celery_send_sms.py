# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from typing import Any
from unittest.mock import create_autospec

import pytest
from celery import Task
from models_library.notifications.celery import SmsContact, SmsMessage
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_notifications.api.celery._sms import send_sms_message_task
from simcore_service_notifications.exceptions.errors import (
    NotificationsSmsDeliveryError,
    NotificationsSmsDeliveryPermanentError,
)
from twilio.base.exceptions import TwilioRestException  # type: ignore[import-untyped]

_TWILIO_SETTINGS = {
    "accounts": {
        "local": {
            "TWILIO_ACCOUNT_SID": "ACdummy",
            "TWILIO_AUTH_TOKEN": "aDummyAuthToken",
            "TWILIO_COUNTRY_CODES_W_ALPHANUMERIC_SID_SUPPORT": ["41"],
        }
    },
    "products": {
        "osparc": {
            "account": "local",
            "messaging_service_sid": "MGdummy",
            "alphanumeric_sender_id": "osparc",
        }
    },
}


@pytest.fixture
def twilio_environment(mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTIFICATIONS_TWILIO_SETTINGS", json.dumps(_TWILIO_SETTINGS))


@pytest.mark.parametrize(
    "status, is_permanent",
    [
        pytest.param(400, True, id="bad request"),
        pytest.param(404, True, id="not found"),
        pytest.param(429, False, id="rate limited by provider"),
        pytest.param(502, False, id="provider unavailable"),
    ],
)
async def test_send_sms_message_task_error_classification(
    twilio_environment: None,
    mocker: Any,
    status: int,
    is_permanent: bool,
):
    mocker.patch(
        "simcore_service_notifications.api.celery._sms.send_sms",
        side_effect=TwilioRestException(
            status=status,
            uri="https://api.twilio.com/2010-04-01/Accounts/ACdummy/Messages.json",
            msg="rejected",
        ),
    )
    message = SmsMessage(to=SmsContact(phone_number="+41777777777"), body="Your code is 123456")

    with pytest.raises(NotificationsSmsDeliveryError) as exc_info:
        await send_sms_message_task(create_autospec(Task, instance=True), "task-key", "osparc", message)

    assert isinstance(exc_info.value, NotificationsSmsDeliveryPermanentError) is is_permanent
