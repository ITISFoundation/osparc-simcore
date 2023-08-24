# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from aiohttp.test_utils import TestClient
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from simcore_service_webserver.application_settings import ApplicationSettings


def test_module_setup_defaults_to_false(client: TestClient):
    assert client.app
    settings: ApplicationSettings = client.app[APP_SETTINGS_KEY]

    assert settings.WEBSERVER_CLUSTERS
    assert "list_clusters" in client.app.router


def test_module_setup_can_be_properly_enabled(
    enable_webserver_clusters_feature: None,
    client: TestClient,
):
    assert client.app
    settings: ApplicationSettings = client.app[APP_SETTINGS_KEY]

    assert settings.WEBSERVER_CLUSTERS
    assert "list_clusters" in client.app.router
