# pylint:disable=redefined-outer-name
# pylint:disable=unused-arguments

import json

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.user_preferences import PreferenceIdentifier, PreferenceName
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_webserver.users._preferences_models import (
    TelemetryLowDiskSpaceWarningThresholdFrontendUserPreference,
    UserInactivityThresholdFrontendUserPreference,
    get_preference_identifier,
    get_preference_name,
)


def test_get_preference_name_and_get_preference_identifier():
    preference_name: PreferenceName = (
        TelemetryLowDiskSpaceWarningThresholdFrontendUserPreference.get_preference_name()
    )
    assert (
        preference_name == "TelemetryLowDiskSpaceWarningThresholdFrontendUserPreference"
    )
    preference_identifier: PreferenceIdentifier = get_preference_identifier(
        preference_name
    )
    assert preference_identifier != preference_name
    assert preference_identifier == "lowDiskSpaceThreshold"

    preference_name_via_identifier: PreferenceName = get_preference_name(
        preference_identifier
    )
    assert preference_name_via_identifier == preference_name


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "USERS_FRONTEND_PREFERENCES_DEFAULTS_OVERWRITES": json.dumps(
                {"UserInactivityThresholdFrontendUserPreference": 3600}
            )
        },
    )


@pytest.fixture
def app(client: TestClient) -> web.Application:
    assert client.app
    return client.app


def test_overwrite_user_preferences_defaults(app: web.Application):
    instance = UserInactivityThresholdFrontendUserPreference()
    assert instance.value == 3600
