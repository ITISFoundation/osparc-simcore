from aiohttp.test_utils import TestClient
from servicelib.application_keys import APP_CONFIG_KEY


def test_module_correctly_setup(client: TestClient):
    cfg = client.app[APP_CONFIG_KEY]
    assert "clusters" in cfg
    assert cfg["clusters"]["enabled"] == True
