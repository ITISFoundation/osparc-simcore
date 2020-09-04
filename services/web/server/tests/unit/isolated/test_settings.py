# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module

from simcore_service_webserver.settings import setup_settings, APP_SETTINGS_KEY


def test_settings_constructs(monkeypatch):
    monkeypatch.setenv("SC_VCS_URL", "FOO")
    app = dict()

    #
    setup_settings(app)

    #
    assert APP_SETTINGS_KEY in app
    settings = app[APP_SETTINGS_KEY]

    assert 'vcs_url' in settings.public_dict()
    assert settings.public_dict()['vcs_url'] == "FOO"

    assert 'app_name' in settings.public_dict()
    assert 'api_version' in settings.public_dict()

    # avoids display of sensitive info
    assert not any( "pass" in key for key in settings.public_dict().keys() )
    assert not any( "token" in key for key in settings.public_dict().keys() )
    assert not any( "secret" in key for key in settings.public_dict().keys() )
