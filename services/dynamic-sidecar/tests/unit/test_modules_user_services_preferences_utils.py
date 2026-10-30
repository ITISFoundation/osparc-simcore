# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from types import SimpleNamespace

import pytest
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.modules.user_services_preferences._utils import (
    get_resolved_version,
    is_feature_enabled,
)


@pytest.fixture
def app_stub(mock_environment: EnvVarsDict) -> SimpleNamespace:
    settings = ApplicationSettings.create_from_envs()
    return SimpleNamespace(state=SimpleNamespace(settings=settings))


def test_get_resolved_version_service_version_mode(
    app_stub: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
):
    setenvs_from_dict(
        monkeypatch,
        {
            "DY_SIDECAR_USER_PREFERENCES_VERSION_SOURCE": "service-version",
            "DY_SIDECAR_SERVICE_VERSION": "1.2.3",
        },
    )
    app_stub.state.settings = ApplicationSettings.create_from_envs()

    assert get_resolved_version(app_stub) == "1.2.3"


def test_get_resolved_version_display_mode_with_valid_semver(
    app_stub: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
):
    setenvs_from_dict(
        monkeypatch,
        {
            "DY_SIDECAR_USER_PREFERENCES_VERSION_SOURCE": "version-display",
            "DY_SIDECAR_SERVICE_VERSION_DISPLAY": "2.0.0",
        },
    )
    app_stub.state.settings = ApplicationSettings.create_from_envs()

    assert get_resolved_version(app_stub) == "2.0.0"


@pytest.mark.parametrize("version_display_env", [{"DY_SIDECAR_SERVICE_VERSION_DISPLAY": "Summer Release"}, {}])
def test_get_resolved_version_display_mode_disables_feature_when_not_a_valid_version(
    app_stub: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    version_display_env: EnvVarsDict,
    caplog: pytest.LogCaptureFixture,
):
    setenvs_from_dict(
        monkeypatch,
        {"DY_SIDECAR_USER_PREFERENCES_VERSION_SOURCE": "version-display", **version_display_env},
    )
    app_stub.state.settings = ApplicationSettings.create_from_envs()

    assert get_resolved_version(app_stub) is None
    assert "not a valid ServiceVersion" in caplog.text


def test_is_feature_enabled_disabled_when_resolved_version_is_none(
    app_stub: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
):
    setenvs_from_dict(
        monkeypatch,
        {"DY_SIDECAR_USER_PREFERENCES_VERSION_SOURCE": "version-display"},
    )
    app_stub.state.settings = ApplicationSettings.create_from_envs()

    assert is_feature_enabled(app_stub) is False
