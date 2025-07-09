# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import json
from typing import Any
from unittest.mock import Mock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.user_preferences import (
    FrontendUserPreference,
    PreferenceIdentifier,
    PreferenceName,
)
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_webserver.application_settings import ApplicationSettings
from simcore_service_webserver.constants import APP_SETTINGS_KEY
from simcore_service_webserver.user_preferences._models import (
    ALL_FRONTEND_PREFERENCES,
    TelemetryLowDiskSpaceWarningThresholdFrontendUserPreference,
    get_preference_identifier,
    get_preference_name,
    overwrite_user_preferences_defaults,
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
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    overwrites: dict[str, Any],
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_USERS": json.dumps(
                {"USERS_FRONTEND_PREFERENCES_DEFAULTS_OVERWRITES": overwrites}
            )
        },
    )


@pytest.fixture
def app(client: TestClient) -> web.Application:
    assert client.app
    return client.app


@pytest.mark.parametrize(
    "overwrites",
    [
        {
            "UserInactivityThresholdFrontendUserPreference": 45,
            "WalletIndicatorVisibilityFrontendUserPreference": "nothing",
            "ServicesFrontendUserPreference": {"empty": "data"},
            "DoNotShowAnnouncementsFrontendUserPreference": [1, 5, 70],
            "ConnectPortsAutomaticallyFrontendUserPreference": False,
        }
    ],
)
def test_overwrite_user_preferences_defaults(
    app: web.Application, overwrites: dict[str, Any]
):
    search_map: dict[str, type[FrontendUserPreference]] = {
        x.__name__: x for x in ALL_FRONTEND_PREFERENCES
    }
    for class_name, expected_default in overwrites.items():
        instance = search_map[class_name]()
        assert instance.value == expected_default


@pytest.fixture
def mock_app(app_environment: EnvVarsDict) -> Mock:
    app = {APP_SETTINGS_KEY: Mock()}
    app[APP_SETTINGS_KEY] = ApplicationSettings.create_from_envs()
    return app  # type: ignore


@pytest.mark.parametrize(
    "overwrites",
    [
        {"WalletIndicatorVisibilityFrontendUserPreference": 34},
        {"UserInactivityThresholdFrontendUserPreference": 34.6},
        {"ServicesFrontendUserPreference": [1, 3, 4]},
        {"ServicesFrontendUserPreference": "str"},
        {"ServicesFrontendUserPreference": 1},
        {"DoNotShowAnnouncementsFrontendUserPreference": {}},
        {"DoNotShowAnnouncementsFrontendUserPreference": 1},
        {"DoNotShowAnnouncementsFrontendUserPreference": 3.4},
    ],
)
def test_overwrite_user_preferences_defaults_wrong_type(
    mock_app: Mock, overwrites: dict[str, Any]
):
    with pytest.raises(TypeError):
        overwrite_user_preferences_defaults(mock_app)
