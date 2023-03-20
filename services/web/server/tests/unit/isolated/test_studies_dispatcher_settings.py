# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from datetime import timedelta

import pytest
from models_library.errors import ErrorDict
from pydantic import ValidationError
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_service_webserver.socketio.handlers_utils import EnvironDict
from simcore_service_webserver.studies_dispatcher.settings import (
    StudiesDispatcherSettings,
)


@pytest.fixture
def environment(monkeypatch: pytest.MonkeyPatch) -> EnvironDict:
    envs = setenvs_from_dict(
        monkeypatch,
        envs=StudiesDispatcherSettings.Config.schema_extra["example"],
    )

    return envs


def test_studies_dispatcher_settings(environment: EnvironDict):

    settings = StudiesDispatcherSettings.create_from_envs()

    assert environment == {
        "STUDIES_GUEST_ACCOUNT_LIFETIME": "2 1:10:00",
        "STUDIES_ACCESS_ANONYMOUS_ALLOWED": "1",
    }

    assert not settings.is_login_required()

    # 2 days 1h and 10 mins
    assert settings.STUDIES_GUEST_ACCOUNT_LIFETIME == timedelta(
        days=2, hours=1, minutes=10
    )


def test_studies_dispatcher_settings_invalid_lifetime(
    environment: EnvironDict, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("STUDIES_GUEST_ACCOUNT_LIFETIME", "-2")

    with pytest.raises(ValidationError) as exc_info:
        StudiesDispatcherSettings.create_from_envs()

    validation_error: ErrorDict = exc_info.value.errors()[0]
    assert "-2" in validation_error.pop("msg", "")
    assert validation_error == {
        "loc": ("STUDIES_GUEST_ACCOUNT_LIFETIME",),
        "type": "value_error",
    }
