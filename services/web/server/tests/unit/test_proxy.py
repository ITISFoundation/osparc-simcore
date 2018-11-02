
from yarl import URL
import pytest

#KEYS = "scheme, user, password, host, port, path, query, query_string, fragment, strict".split(", ")


@pytest.fixture
def backend_service():
    """ Server behind web-server """
    pass

@pytest.fixture
def direct_client(backend_service):
    """ Directly communicates with backend-service, e.g. notebooks """
    pass

@pytest.fixture
def webserver():


@pytest.fixture
def service_cfg():

@pytest.fixture
def indirect_client(webserver):
    pass



def test_http_proxy(indirect_client, direct_client):

    # service configuration
    cfg = {
        'scheme': 'http',
        'host': 'localhost',
        'port': 8090,
        'token': 'N1Hrb_SnB',
    }

    KEYS = "scheme host port".split()
    base_url = URL.build(**{k:cfg[k] for k in KEYS})
    direct_url = base_url.with_path("/foo/").with_query({"a": 5}).with_fragment("frag")

    proxy_path = direct_url.relative()

    mount_point = URL("/pxy/{token}".format(**cfg))
    url = mount_point.join(proxy_path)

    resp1 = await indirect_client.get(url)
    resp2 = await direct_client.get(direct_url)

    resp1 = await indirect_client.post(url)
    resp2 = await direct_client.post(direct_url)
