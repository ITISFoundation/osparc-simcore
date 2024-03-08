from unittest.mock import MagicMock

import pytest
from pydantic import EmailStr
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    env_devel_dict: EnvVarsDict,
    external_environment: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **env_devel_dict,
            **external_environment,
        },
    )


@pytest.fixture
def smtp_mock_or_none(
    mocker: MockerFixture, external_user_email: EmailStr | None
) -> MagicMock | None:
    if not external_user_email:
        return mocker.patch("notifications_library._email.SMTP")
    print("🚨 Emails might be sent to", external_user_email)
    return None
