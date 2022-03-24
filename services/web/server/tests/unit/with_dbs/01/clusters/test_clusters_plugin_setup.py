# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from aiohttp.test_utils import TestClient
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from simcore_service_webserver.application_settings import ApplicationSettings


def test_module_setup_skipped_when_no_dev_features_enabled(client: TestClient):
    assert client.app
    settings: ApplicationSettings = client.app[APP_SETTINGS_KEY]

    assert not settings.WEBSERVER_CLUSTERS
    assert "list_clusters_handler" not in client.app.router


def test_module_setup_applied_when_dev_features_enabled(
    enable_dev_features: None, client: TestClient
):
    assert client.app
    settings: ApplicationSettings = client.app[APP_SETTINGS_KEY]

    assert settings.WEBSERVER_CLUSTERS
    assert "list_clusters_handler" in client.app.router
