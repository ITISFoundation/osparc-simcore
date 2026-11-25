# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from unittest.mock import create_autospec

import pytest
from aiohttp import web
from models_library.notifications.errors import (
    NotificationsNoActiveRecipientsError,
    NotificationsRecipientChannelMismatchError,
)
from simcore_service_webserver.notifications._models import EmailContact, SmsContact
from simcore_service_webserver.notifications._service import (
    _create_email_addressing,
    _create_sms_addressing,
)

_EMAIL = EmailContact(name="Alice", email="alice@example.com")
_SMS = SmsContact(phone_number="+41777777777")


@pytest.fixture
def app() -> web.Application:
    return create_autospec(web.Application, instance=True)


async def test_email_addressing_keeps_email_contacts(app: web.Application):
    addressing = await _create_email_addressing(
        app,
        group_ids=None,
        external_contacts=[_EMAIL],
        reply_to=_EMAIL,
        bcc=[_EMAIL],
    )

    assert addressing.to == [_EMAIL]
    assert addressing.reply_to == _EMAIL
    assert addressing.bcc == [_EMAIL]


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({"external_contacts": [_EMAIL, _SMS]}, id="to-mixed"),
        pytest.param({"external_contacts": [_EMAIL], "reply_to": _SMS}, id="reply-to-sms"),
        pytest.param({"external_contacts": [_EMAIL], "bcc": [_SMS]}, id="bcc-sms"),
    ],
)
async def test_email_addressing_rejects_sms_contacts(app: web.Application, kwargs: dict):
    with pytest.raises(NotificationsRecipientChannelMismatchError):
        await _create_email_addressing(app, group_ids=None, **kwargs)


def test_sms_addressing_keeps_sms_contacts():
    addressing = _create_sms_addressing([_SMS])

    assert addressing.to == [_SMS]


def test_sms_addressing_rejects_email_contacts():
    with pytest.raises(NotificationsRecipientChannelMismatchError):
        _create_sms_addressing([_SMS, _EMAIL])


async def test_email_addressing_without_recipients_raises(app: web.Application):
    with pytest.raises(NotificationsNoActiveRecipientsError):
        await _create_email_addressing(app, group_ids=None, external_contacts=None)


def test_sms_addressing_without_recipients_raises():
    with pytest.raises(NotificationsNoActiveRecipientsError):
        _create_sms_addressing([])
