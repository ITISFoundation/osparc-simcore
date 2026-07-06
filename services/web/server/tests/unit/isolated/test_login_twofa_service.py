# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from common_library.gettext_support import DEFAULT_LOCALE
from simcore_service_webserver.login._twofa_service import send_sms_code

_PHONE_NUMBER = "+41000000000"
_CODE = "123456"
_FIRST_NAME = "Jane"


@pytest.fixture
def mock_twilio_client() -> Iterator[MagicMock]:
    with patch("simcore_service_webserver.login._twofa_service.twilio.rest.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        yield mock_client


async def _send_sms_code(
    *,
    locale: str | None,
    user_id: int | None = None,
    resolved_locale: str = DEFAULT_LOCALE,
) -> AsyncMock:
    mock_app = MagicMock()
    mock_twilio_auth = MagicMock()
    mock_twilio_auth.is_alphanumeric_supported.return_value = False

    with patch(
        "simcore_service_webserver.login._twofa_service.resolve_effective_locale",
        new_callable=AsyncMock,
        return_value=resolved_locale,
    ) as mock_resolve:
        await send_sms_code(
            mock_app,
            phone_number=_PHONE_NUMBER,
            code=_CODE,
            twilio_auth=mock_twilio_auth,
            twilio_messaging_sid="sid",
            twilio_alpha_numeric_sender="sender",
            first_name=_FIRST_NAME,
            product_name="osparc",
            user_id=user_id,
            locale=locale,
        )
    return mock_resolve


async def test_send_sms_code_translates_body_using_resolved_locale(mock_twilio_client: MagicMock):
    """The SMS body is translated via the locale resolved by resolve_effective_locale."""
    translated_msgid = "Estimado/a {first_name}, su código de verificación es {code}"

    with patch("simcore_service_webserver.login._twofa_service.get_translator") as mock_get_translator:
        mock_get_translator.return_value.gettext.return_value = translated_msgid
        await _send_sms_code(locale="es_ES", resolved_locale="es_ES")

    mock_get_translator.assert_called_once_with("es_ES")
    body = mock_twilio_client.messages.create.call_args.kwargs["body"]
    assert body == translated_msgid.format(first_name=_FIRST_NAME, code=_CODE)


async def test_send_sms_code_forwards_locale_and_user_id_to_resolver(mock_twilio_client: MagicMock):
    """send_sms_code delegates locale resolution, passing through the caller's locale/user_id."""
    mock_resolve = await _send_sms_code(locale=None, user_id=42)

    mock_resolve.assert_awaited_once()
    _, kwargs = mock_resolve.call_args
    assert kwargs["user_id"] == 42
    assert kwargs["locale"] is None
    assert kwargs["product_name"] == "osparc"
    mock_twilio_client.messages.create.assert_called_once()


async def test_send_sms_code_falls_back_to_english_by_default(mock_twilio_client: MagicMock):
    """With no explicit locale and no user_id, the body stays in English (DEFAULT_LOCALE, no catalog)."""
    await _send_sms_code(locale=None, user_id=None, resolved_locale=DEFAULT_LOCALE)

    body = mock_twilio_client.messages.create.call_args.kwargs["body"]
    assert body == f"Dear {_FIRST_NAME}, your verification code is {_CODE}"
