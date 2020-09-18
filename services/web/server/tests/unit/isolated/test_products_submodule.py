# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
from yarl import URL

from simcore_service_webserver.constants import (
    APP_PRODUCTS_KEY,
    RQ_PRODUCT_KEY,
    X_PRODUCT_NAME_HEADER,
)
from simcore_service_webserver.products import (
    FRONTEND_APP_DEFAULT,
    Product,
    discover_product_middleware,
)


@pytest.fixture()
def mock_postgres_product_table():
    # NOTE: try here your product host_regex before adding them in the database!
    return [
        dict(name="osparc", host_regex=r"([\.-]{0,1}osparc[\.-])"),
        dict(
            name="s4l",
            host_regex=r"(^s4l[\.-])|(^sim4life\.)|(^api.s4l[\.-])|(^api.sim4life\.)",
        ),
        dict(name="tis", host_regex=r"(^tis[\.-])|(^ti-solutions\.)"),
    ]


@pytest.fixture
def mock_app(mock_postgres_product_table):
    class MockApp(dict):
        def __init__(self):
            super().__init__()
            self.middlewares = []

    mock_app = MockApp()
    mock_app[APP_PRODUCTS_KEY] = [
        Product(**entry) for entry in mock_postgres_product_table
    ]

    return mock_app


@pytest.mark.parametrize(
    "request_url,product_from_client,expected_product",
    [
        ("https://tis-master.domain.io/", "tis", "tis"),
        ("https://s4l-staging.domain.com/v0/", "s4l", "s4l"),
        ("https://osparc-master.domain.com/v0/projects", None, "osparc"),
        ("https://s4l.domain.com/", "s4l", "s4l"),
        ("https://some-valid-but-undefined-product.io/", None, FRONTEND_APP_DEFAULT),
        ("https://sim4life.io/", "s4l", "s4l"),
        ("https://api.sim4life.io/", None, "s4l"),  # e.g. api client is not set
        ("https://ti-solutions.io/", "tis", "tis"),
        ("https://osparc.io/", None, "osparc"),  # e.g. an old front-end
        ("https://staging.osparc.io/", "osparc", "osparc"),
    ],
)
async def test_middleware_product_discovery(
    request_url, product_from_client, expected_product, mock_app
):
    """
    A client's request reaches the middleware with
        - an url (request_url),
        - a product name in the header from client (product_from_client)
    """
    requested_url = URL(request_url)

    # mocks
    class MockRequest(dict):
        @property
        def headers(self):
            return (
                {X_PRODUCT_NAME_HEADER: product_from_client}
                if product_from_client
                else {}
            )

        @property
        def app(self):
            return mock_app

        @property
        def path(self):
            return requested_url.path

        @property
        def host(self):
            return requested_url.host

    mock_request = MockRequest()

    async def mock_handler(request):
        return "OK"

    # under test ---------
    response = await discover_product_middleware(mock_request, mock_handler)

    # checks
    assert mock_request[RQ_PRODUCT_KEY] == expected_product
