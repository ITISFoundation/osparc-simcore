# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from datetime import timedelta

import pytest
from models_library.errors import ErrorDict
from pydantic import ValidationError
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_webserver.studies_dispatcher.settings import (
    StudiesDispatcherSettings,
)


@pytest.fixture
def environment(monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    envs = setenvs_from_dict(
        monkeypatch,
        envs=StudiesDispatcherSettings.model_config["json_schema_extra"]["example"],
    )
    return envs


def test_studies_dispatcher_settings(environment: EnvVarsDict):
    settings = StudiesDispatcherSettings.create_from_envs()

    assert environment == {
        "STUDIES_GUEST_ACCOUNT_LIFETIME": "2 1:10:00",
        "STUDIES_ACCESS_ANONYMOUS_ALLOWED": "1",
    }

    assert not settings.is_login_required()

    # 2 days 1h and 10 mins
    assert (
        timedelta(days=2, hours=1, minutes=10)
        == settings.STUDIES_GUEST_ACCOUNT_LIFETIME
    )


def test_studies_dispatcher_settings_invalid_lifetime(
    environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("STUDIES_GUEST_ACCOUNT_LIFETIME", "-2")

    with pytest.raises(ValidationError) as exc_info:
        StudiesDispatcherSettings.create_from_envs()

    validation_error: ErrorDict = next(iter(exc_info.value.errors()))
    assert validation_error["loc"] == ("STUDIES_GUEST_ACCOUNT_LIFETIME",)
    assert "-2" in validation_error["msg"]
    assert validation_error["type"] == "value_error"
