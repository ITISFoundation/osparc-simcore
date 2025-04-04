from unittest.mock import MagicMock

import pytest
from pydantic import EmailStr
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    env_devel_dict: EnvVarsDict,
    external_envfile_dict: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(monkeypatch, {**env_devel_dict, **external_envfile_dict})


@pytest.fixture
def smtp_mock_or_none(
    mocker: MockerFixture, is_external_user_email: EmailStr | None, user_email: EmailStr
) -> MagicMock | None:
    if not is_external_user_email:
        return mocker.patch("notifications_library._email.SMTP")
    print("🚨 Emails might be sent to", f"{user_email=}")
    return None
