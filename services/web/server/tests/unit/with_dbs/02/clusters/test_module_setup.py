# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from aiohttp.test_utils import TestClient
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY


def test_module_setup_skipped_when_no_dev_features_enabled(client: TestClient):
    cfg = client.app[APP_CONFIG_KEY]
    assert "clusters" in cfg
    assert cfg["clusters"]["enabled"] == True

    assert "list_clusters_handler" not in client.app.router


def test_module_setup_applied_when_dev_features_enabled(
    enable_dev_features: None, client: TestClient
):
    cfg = client.app[APP_CONFIG_KEY]
    assert "clusters" in cfg
    assert cfg["clusters"]["enabled"] == True

    assert "list_clusters_handler" in client.app.router
