# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module

import json

import pytest
from aiohttp import web
from common_library.json_serialization import json_dumps
from pydantic import HttpUrl, TypeAdapter
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_webserver.application_settings import (
    APP_SETTINGS_KEY,
    ApplicationSettings,
    setup_settings,
)


@pytest.fixture
def app_settings(
    mock_webserver_service_environment: EnvVarsDict,
) -> ApplicationSettings:
    app = web.Application()

    print("envs\n", json.dumps(mock_webserver_service_environment, indent=1))

    # init and validation happens here
    settings = setup_settings(app)
    print("settings:\n", settings.model_dump_json(indent=1))

    assert APP_SETTINGS_KEY in app
    assert app[APP_SETTINGS_KEY] == settings
    return settings


def test_settings_constructs(app_settings: ApplicationSettings):
    assert "vcs_url" in app_settings.public_dict()
    assert (
        app_settings.public_dict()["vcs_url"]
        == "git@github.com:ITISFoundation/osparc-simcore.git"
    )

    assert "app_name" in app_settings.public_dict()
    assert "api_version" in app_settings.public_dict()

    # assert can jsonify w/o raising
    print("public_dict:", json_dumps(app_settings.public_dict(), indent=1))


def test_settings_to_client_statics(app_settings: ApplicationSettings):
    statics = app_settings.to_client_statics()

    # assert can jsonify w/o raising
    print("statics:", json_dumps(statics, indent=1))

    # all key in camelcase
    assert all(
        key[0] == key[0].lower() and "_" not in key and key.lower() != key
        for key in statics
    ), f"Got {list(statics.keys())}"

    # special alias
    assert statics["stackName"] == "master-simcore"
    assert statics["pluginsDisabled"] == ["WEBSERVER_CLUSTERS"]


def test_settings_to_client_statics_plugins(
    mock_webserver_service_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
):
    disable_plugins = {"WEBSERVER_EXPORTER", "WEBSERVER_SCICRUNCH"}
    for name in disable_plugins:
        monkeypatch.setenv(name, "null")

    monkeypatch.setenv("WEBSERVER_VERSION_CONTROL", "0")
    disable_plugins.add("WEBSERVER_VERSION_CONTROL")

    monkeypatch.setenv("WEBSERVER_FOLDERS", "0")
    disable_plugins.add("WEBSERVER_FOLDERS")

    settings = ApplicationSettings.create_from_envs()
    statics = settings.to_client_statics()

    print("STATICS:\n", json_dumps(statics, indent=1))

    assert settings.WEBSERVER_LOGIN

    assert (
        statics["webserverLogin"]["LOGIN_ACCOUNT_DELETION_RETENTION_DAYS"]
        == settings.WEBSERVER_LOGIN.LOGIN_ACCOUNT_DELETION_RETENTION_DAYS
    )
    assert (
        statics["webserverLogin"]["LOGIN_2FA_REQUIRED"]
        == settings.WEBSERVER_LOGIN.LOGIN_2FA_REQUIRED
    )
    assert (
        statics["webserverSession"].get("SESSION_COOKIE_MAX_AGE")
        == settings.WEBSERVER_SESSION.SESSION_COOKIE_MAX_AGE
    )

    assert statics["vcsReleaseTag"]
    assert TypeAdapter(HttpUrl).validate_python(statics["vcsReleaseUrl"])

    assert set(statics["pluginsDisabled"]) == (disable_plugins | {"WEBSERVER_CLUSTERS"})


@pytest.mark.parametrize("is_dev_feature_enabled", [True, False])
@pytest.mark.parametrize(
    "plugin_name",
    ["WEBSERVER_META_MODELING", "WEBSERVER_VERSION_CONTROL"]
    # NOTE: this is the list in _enable_only_if_dev_features_allowed
)
def test_disabled_plugins_settings_to_client_statics(
    is_dev_feature_enabled: bool,
    mock_webserver_service_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    plugin_name: str,
):
    monkeypatch.setenv(
        "WEBSERVER_DEV_FEATURES_ENABLED", f"{is_dev_feature_enabled}".lower()
    )

    settings = ApplicationSettings.create_from_envs()
    statics = settings.to_client_statics()

    # checks whether it is shown to the front-end depending on the value of WEBSERVER_DEV_FEATURES_ENABLED
    if is_dev_feature_enabled:
        assert plugin_name not in set(statics["pluginsDisabled"])
    else:
        assert plugin_name in set(statics["pluginsDisabled"])


def test_avoid_sensitive_info_in_public(app_settings: ApplicationSettings):
    # avoids display of sensitive info
    assert not any("pass" in key for key in app_settings.public_dict())
    assert not any("token" in key for key in app_settings.public_dict())
    assert not any("secret" in key for key in app_settings.public_dict())
    assert not any("private" in key for key in app_settings.public_dict())
