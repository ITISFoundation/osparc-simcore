# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Any

import pytest
from simcore_postgres_database.models.products import LOGIN_SETTINGS_DEFAULT
from simcore_postgres_database.webserver_models import products
from simcore_service_webserver._constants import X_PRODUCT_NAME_HEADER
from simcore_service_webserver.products._events import _set_app_state
from simcore_service_webserver.products._middlewares import discover_product_middleware
from simcore_service_webserver.products._model import Product
from simcore_service_webserver.products.api import get_product_name
from simcore_service_webserver.statics._constants import FRONTEND_APP_DEFAULT
from yarl import URL


@pytest.fixture()
def mock_postgres_product_table():
    # NOTE: try here your product's host_regex before adding them in the database!
    column_defaults = {
        c.name: f"{c.server_default.arg}" for c in products.columns if c.server_default
    }

    column_defaults["login_settings"] = LOGIN_SETTINGS_DEFAULT

    return [
        dict(name="osparc", host_regex=r"([\.-]{0,1}osparc[\.-])", **column_defaults),
        dict(
            name="s4l",
            host_regex=r"(^s4l[\.-])|(^sim4life\.)|(^api.s4l[\.-])|(^api.sim4life\.)",
            **column_defaults,
        ),
        dict(
            name="tis",
            host_regex=r"(^tis[\.-])|(^ti-solutions\.)",
            vendor={
                "name": "ACME",
                "address": "sesame street",
                "copyright": "© ACME correcaminos",
                "url": "https://acme.com",
                "forum_url": "https://forum.acme.com",
            },
            **column_defaults,
        ),
    ]


@pytest.fixture
def mock_app(mock_postgres_product_table: dict[str, Any]):
    class MockApp(dict):
        def __init__(self):
            super().__init__()
            self.middlewares = []

    mock_app = MockApp()

    app_products: dict[str, Product] = {
        entry["name"]: Product(**entry) for entry in mock_postgres_product_table
    }
    default_product_name = next(iter(app_products.keys()))
    _set_app_state(mock_app, app_products, default_product_name)

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
    request_url, product_from_client, expected_product: str, mock_app
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
    assert get_product_name(mock_request) == expected_product
