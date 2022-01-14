# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module

import json

import pytest
from aiohttp import web
from simcore_service_webserver.application_settings import (
    APP_SETTINGS_KEY,
    ApplicationSettings,
    setup_settings,
)


@pytest.fixture
def settings(monkeypatch) -> ApplicationSettings:
    monkeypatch.setenv("SC_VCS_URL", "git@github.com:ITISFoundation/osparc-simcore.git")
    monkeypatch.setenv("SWARM_STACK_NAME", "simcore_stack")
    monkeypatch.setenv("STACK_NAME", "invalid_env")
    monkeypatch.setenv("WEBSERVER_MANUAL_MAIN_URL", "http://some_doc.org")
    monkeypatch.setenv("WEBSERVER_POSTGRES", "null")
    monkeypatch.setenv("WEBSERVER_SESSION_SECRET_KEY", "1" * 32)
    monkeypatch.setenv("WEBSERVER_STUDIES_ACCESS_ENABLED", "1")

    app = web.Application()

    # init and validation happens here
    setup_settings(app)

    assert APP_SETTINGS_KEY in app
    return app[APP_SETTINGS_KEY]


def test_settings_constructs(settings: ApplicationSettings):
    assert "vcs_url" in settings.public_dict()
    assert (
        settings.public_dict()["vcs_url"]
        == "git@github.com:ITISFoundation/osparc-simcore.git"
    )

    assert "app_name" in settings.public_dict()
    assert "api_version" in settings.public_dict()


def test_settings_to_client_statics(settings: ApplicationSettings):
    statics = settings.to_client_statics()

    # all key in camelcase
    assert all(
        key[0] == key[0].lower() and "_" not in key and key.lower() != key
        for key in statics.keys()
    ), f"Got {list(statics.keys())}"

    # special alias
    assert statics["stackName"] == "simcore_stack"

    # can jsonify
    print(json.dumps(statics))


def test_avoid_sensitive_info_in_public(settings: ApplicationSettings):
    # avoids display of sensitive info
    assert not any("pass" in key for key in settings.public_dict().keys())
    assert not any("token" in key for key in settings.public_dict().keys())
    assert not any("secret" in key for key in settings.public_dict().keys())
