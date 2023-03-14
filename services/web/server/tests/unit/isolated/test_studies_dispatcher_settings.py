from datetime import datetime, timedelta, timezone

import pytest
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
        "STUDIES_GUEST_ACCOUNT_LIFETIME": "2 1:10:00",  # 2 days 1h and
        "STUDIES_ACCESS_ANONYMOUS_ALLOWED": "1",
    }

    assert settings.is_login_required()
    # 2 days 1h and 10 mins
    assert settings.STUDIES_GUEST_ACCOUNT_LIFETIME.days == 2
    assert settings.STUDIES_GUEST_ACCOUNT_LIFETIME.hour == 1
    assert settings.STUDIES_GUEST_ACCOUNT_LIFETIME.min == 10

    after_tomorrow = datetime.now(timezone.utc) + timedelta(days=2)
    assert settings.get_guest_expiration().day == after_tomorrow.day
