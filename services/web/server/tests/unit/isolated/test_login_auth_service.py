# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from simcore_service_webserver.login import _auth_service
from simcore_service_webserver.login.errors import WrongPasswordError


async def test_unknown_user_is_verified_against_dummy_hash_and_rejected(mocker: MockerFixture):
    mock_check_password = mocker.patch.object(_auth_service.security_service, "check_password", return_value=False)
    product = SimpleNamespace(name="osparc")

    with pytest.raises(WrongPasswordError) as exc_info:
        await _auth_service.check_authorized_user_credentials(
            MagicMock(),
            None,
            password="some-password",  # noqa: S106
            product=product,  # type: ignore[arg-type]
        )

    assert exc_info.value.error_context()["user_id"] is None
    mock_check_password.assert_called_once_with("some-password", _auth_service._get_dummy_password_hash())  # noqa: SLF001
    assert _auth_service._get_dummy_password_hash().startswith("$argon2id$")  # noqa: SLF001
