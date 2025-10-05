# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module

import json
from typing import Annotated

import pytest
from aiohttp import web
from common_library.json_serialization import json_dumps
from pydantic import Field, HttpUrl, TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_webserver.application_settings import (
    _X_FEATURE_UNDER_DEVELOPMENT,
    APP_SETTINGS_APPKEY,
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

    assert APP_SETTINGS_APPKEY in app
    assert app[APP_SETTINGS_APPKEY] == settings
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
    assert statics["pluginsDisabled"] == [
        "WEBSERVER_META_MODELING",
        "WEBSERVER_VERSION_CONTROL",
    ]


def test_settings_to_client_statics_plugins(
    mock_webserver_service_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
):
    setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_DEV_FEATURES_ENABLED": "1",
        },
    )
    monkeypatch.delenv("WEBSERVER_REALTIME_COLLABORATION", raising=False)

    # explicitly disable these plugins
    disable_plugins = {
        "WEBSERVER_EXPORTER",
        "WEBSERVER_SCICRUNCH",
        "WEBSERVER_META_MODELING",
        "WEBSERVER_VERSION_CONTROL",
    }
    for name in disable_plugins:
        monkeypatch.setenv(name, "null")

    # explicitly disable WEBSERVER_FOLDERS
    monkeypatch.setenv("WEBSERVER_FOLDERS", "0")
    disable_plugins.add("WEBSERVER_FOLDERS")

    # set WEBSERVER_REALTIME_COLLABORATION (NOTE: for now WEBSERVER_DEV_FEATURES_ENABLED=True) )
    monkeypatch.setenv(
        "WEBSERVER_REALTIME_COLLABORATION", '{"RTC_MAX_NUMBER_OF_USERS":3}'
    )

    settings = ApplicationSettings.create_from_envs()
    assert settings.WEBSERVER_DEV_FEATURES_ENABLED

    # -------------

    statics = settings.to_client_statics()
    print("STATICS:\n", json_dumps(statics, indent=1))

    assert settings.WEBSERVER_LOGIN

    assert "webserverLicenses" not in statics
    assert "webserverDevFeaturesEnabled" in statics

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

    # check WEBSERVER_REALTIME_COLLABORATION enabled
    assert "WEBSERVER_REALTIME_COLLABORATION" not in statics["pluginsDisabled"]
    assert settings.WEBSERVER_REALTIME_COLLABORATION
    assert (
        statics["webserverRealtimeCollaboration"]["RTC_MAX_NUMBER_OF_USERS"]
        == settings.WEBSERVER_REALTIME_COLLABORATION.RTC_MAX_NUMBER_OF_USERS
    )

    # check disabled plugins
    assert set(statics["pluginsDisabled"]) == (disable_plugins)


@pytest.mark.parametrize("is_dev_feature_enabled", [True, False])
def test_disabled_plugins_settings_to_client_statics(
    is_dev_feature_enabled: bool,
    mock_webserver_service_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
):
    setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_DEV_FEATURES_ENABLED": f"{is_dev_feature_enabled}".lower(),
            "TEST_FOO": "1",
            "TEST_BAR": "42",
        },
    )

    class DevSettings(ApplicationSettings):
        TEST_FOO: Annotated[
            bool, Field(json_schema_extra={_X_FEATURE_UNDER_DEVELOPMENT: True})
        ]
        TEST_BAR: Annotated[
            int | None, Field(json_schema_extra={_X_FEATURE_UNDER_DEVELOPMENT: True})
        ]

    settings = DevSettings.create_from_envs()

    if is_dev_feature_enabled:
        assert settings.WEBSERVER_DEV_FEATURES_ENABLED is True

        assert settings.TEST_FOO is True
        assert settings.TEST_BAR == 42
    else:
        assert settings.WEBSERVER_DEV_FEATURES_ENABLED is False

        assert settings.TEST_FOO is False
        assert settings.TEST_BAR is None


@pytest.mark.filterwarnings("ignore::aiohttp.web_exceptions.NotAppKeyWarning")
@pytest.mark.filterwarnings("error")
def test_avoid_sensitive_info_in_public(app_settings: ApplicationSettings):
    # avoids display of sensitive info
    assert not any("pass" in key for key in app_settings.public_dict())
    assert not any("token" in key for key in app_settings.public_dict())
    assert not any("secret" in key for key in app_settings.public_dict())
    assert not any("private" in key for key in app_settings.public_dict())


def test_backwards_compatibility_with_bool_env_vars_turned_into_objects(
    monkeypatch: pytest.MonkeyPatch,
    mock_webserver_service_environment: EnvVarsDict,
):
    # Sometimes we turn `WEBSERVER_VAR: bool` into `WEBSERVER_VAR: VarSettings`
    with monkeypatch.context() as patch:
        patch.setenv("WEBSERVER_LICENSES", "true")

        settings = ApplicationSettings.create_from_envs()
        assert settings.WEBSERVER_LICENSES is True

    with monkeypatch.context() as patch:
        patch.setenv("WEBSERVER_LICENSES", "{}")
        patch.setenv("LICENSES_ITIS_VIP_SYNCER_ENABLED", "1")
        patch.setenv("LICENSES_ITIS_VIP_API_URL", "https://some-api/{category}")
        patch.setenv(
            "LICENSES_ITIS_VIP_CATEGORIES",
            '{"HumanWholeBody": "Humans", "HumanBodyRegion": "Humans (Region)", "AnimalWholeBody": "Animal"}',
        )

        settings = ApplicationSettings.create_from_envs()
        assert settings.WEBSERVER_LICENSES is not None
        assert not isinstance(settings.WEBSERVER_LICENSES, bool)
        assert settings.WEBSERVER_LICENSES.LICENSES_ITIS_VIP
        assert settings.WEBSERVER_LICENSES.LICENSES_ITIS_VIP.LICENSES_ITIS_VIP_API_URL
        assert settings.WEBSERVER_LICENSES.LICENSES_ITIS_VIP_SYNCER_ENABLED

    with monkeypatch.context() as patch:
        patch.setenv("WEBSERVER_LICENSES", "null")

        settings = ApplicationSettings.create_from_envs()
        assert settings.WEBSERVER_LICENSES is None


def test_valid_application_settings(mock_webserver_service_environment: EnvVarsDict):
    assert mock_webserver_service_environment

    settings = ApplicationSettings()  # type: ignore
    assert settings

    assert settings == ApplicationSettings.create_from_envs()
