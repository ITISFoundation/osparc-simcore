# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from common_library.gettext_support import SupportedLocale
from models_library.celery import TaskState, TaskStatus
from models_library.notifications import Channel
from models_library.progress_bar import ProgressReport
from models_library.users import UserID
from simcore_service_webserver.login._twofa_service import send_sms_code
from simcore_service_webserver.login.errors import SendingVerificationSmsError

_PHONE_NUMBER = "+14155552671"
_CODE = "123456"
_FIRST_NAME = "Jane"
_USER_NAME = "jane.doe"
_PRODUCT_NAME = "osparc"
_HOST = "https://osparc.example.com"
_TTL = 300
_TASK_UUID = uuid4()


def _task_status(state: TaskState) -> TaskStatus:
    return TaskStatus(
        task_uuid=_TASK_UUID,
        task_state=state,
        progress_report=ProgressReport(actual_value=1),
    )


@pytest.fixture
def mock_send_message_from_template() -> Iterator[AsyncMock]:
    with patch(
        "simcore_service_webserver.login._twofa_service.notifications_service.send_message_from_template",
        new_callable=AsyncMock,
        return_value=(_TASK_UUID, "send_sms_message_task"),
    ) as mock_send:
        yield mock_send


@pytest.fixture(autouse=True)
def mock_get_message_status() -> Iterator[AsyncMock]:
    # delivery completes successfully unless a test overrides the return
    with patch(
        "simcore_service_webserver.login._twofa_service.notifications_service.get_message_status",
        new_callable=AsyncMock,
        return_value=_task_status(TaskState.SUCCESS),
    ) as mock_status:
        yield mock_status


async def _send_sms_code(
    *,
    locale: SupportedLocale | None,
    user_id: UserID | None = None,
) -> None:
    await send_sms_code(
        MagicMock(),
        phone_number=_PHONE_NUMBER,
        code=_CODE,
        first_name=_FIRST_NAME,
        user_name=_USER_NAME,
        product_name=_PRODUCT_NAME,
        host=_HOST,
        ttl=_TTL,
        user_id=user_id,
        locale=locale,
    )


async def test_send_sms_code_forwards_locale_and_user_id_to_notifications(
    mock_send_message_from_template: AsyncMock,
):
    """send_sms_code delegates locale resolution to the notifications service, passing the caller's locale/user_id."""
    await _send_sms_code(locale=None, user_id=UserID(42))

    mock_send_message_from_template.assert_awaited_once()
    _, kwargs = mock_send_message_from_template.call_args
    assert kwargs["user_id"] == 42
    assert kwargs["locale"] is None
    assert kwargs["product_name"] == _PRODUCT_NAME
    assert kwargs["channel"] == Channel.sms
    assert kwargs["template_name"] == "new_2fa_code"


async def test_send_sms_code_sends_code_to_phone_contact(
    mock_send_message_from_template: AsyncMock,
):
    await _send_sms_code(locale="es_ES", user_id=None)

    _, kwargs = mock_send_message_from_template.call_args
    assert [contact.phone_number for contact in kwargs["external_contacts"]] == [_PHONE_NUMBER]
    assert kwargs["locale"] == "es_ES"
    assert kwargs["context"] == {
        "user": {"first_name": _FIRST_NAME, "user_name": _USER_NAME},
        "host": _HOST,
        "code": _CODE,
        "ttl": _TTL,
    }


async def test_send_sms_code_wraps_delivery_failures(
    mock_send_message_from_template: AsyncMock,
):
    mock_send_message_from_template.side_effect = RuntimeError("notifications unavailable")

    with pytest.raises(SendingVerificationSmsError):
        await _send_sms_code(locale=None)


async def test_send_sms_code_polls_delivery_status_of_published_task(
    mock_send_message_from_template: AsyncMock,
    mock_get_message_status: AsyncMock,
):
    await _send_sms_code(locale=None, user_id=UserID(42))

    mock_get_message_status.assert_awaited_once()
    _, kwargs = mock_get_message_status.call_args
    assert kwargs["task_or_group_uuid"] == _TASK_UUID
    assert kwargs["user_id"] == 42
    assert kwargs["product_name"] == _PRODUCT_NAME


async def test_send_sms_code_raises_when_delivery_fails(
    mock_send_message_from_template: AsyncMock,
    mock_get_message_status: AsyncMock,
):
    mock_get_message_status.return_value = _task_status(TaskState.FAILURE)

    with pytest.raises(SendingVerificationSmsError):
        await _send_sms_code(locale=None)


async def test_send_sms_code_reports_success_when_delivery_still_running(
    mock_send_message_from_template: AsyncMock,
    mock_get_message_status: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
):
    # a delivery not finished at the deadline is reported as sent: the task may
    # still deliver, and raising would free the resend cooldown for duplicates
    mock_get_message_status.return_value = _task_status(TaskState.PENDING)
    monkeypatch.setattr("simcore_service_webserver.login._twofa_service._SMS_DELIVERY_MAX_WAIT_S", 0.0)

    await _send_sms_code(locale=None)
    assert mock_get_message_status.await_count >= 1
