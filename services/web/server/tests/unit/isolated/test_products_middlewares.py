# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from servicelib.aiohttp import status
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER
from simcore_postgres_database.models.products import LOGIN_SETTINGS_DEFAULT
from simcore_postgres_database.webserver_models import products
from simcore_service_webserver.products._events import _set_app_state
from simcore_service_webserver.products._middlewares import discover_product_middleware
from simcore_service_webserver.products._model import Product
from simcore_service_webserver.products.api import get_product_name
from simcore_service_webserver.statics._constants import FRONTEND_APP_DEFAULT
from yarl import URL


@pytest.fixture()
def mock_postgres_product_table():
    # NOTE: try here your product's host_regex before adding them in the database!
    column_defaults: dict[str, Any] = {
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
def mock_app(mock_postgres_product_table: dict[str, Any]) -> web.Application:
    app = web.Application()

    app_products: dict[str, Product] = {
        entry["name"]: Product(**entry) for entry in mock_postgres_product_table
    }
    default_product_name = next(iter(app_products.keys()))
    _set_app_state(app, app_products, default_product_name)

    return app


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
        # new auth of subdomains. SEE https://github.com/ITISFoundation/osparc-simcore/pull/6484
        (
            "https://34c878cd-f801-433f-9ddb-7dccba9251af.services.s4l-solutions.com/notebooks/lab",
            "s4l",
            "s4l",
        ),
    ],
)
async def test_middleware_product_discovery(
    request_url: str,
    product_from_client: str | None,
    expected_product: str,
    mock_app: web.Application,
):
    """
    A client's request reaches the middleware with
        - an url (request_url),
        - a product name in the header from client (product_from_client)
    """
    url = URL(request_url)
    headers = {
        "Host": url.host,
    }
    if product_from_client:
        headers.update({X_PRODUCT_NAME_HEADER: product_from_client})

    mock_request = make_mocked_request(
        "GET",
        url.path,
        headers=headers,
        app=mock_app,
    )

    async def _mock_handler(_request: web.Request):
        return web.Response(text="OK")

    # run middleware
    response = await discover_product_middleware(mock_request, _mock_handler)

    # checks
    assert get_product_name(mock_request) == expected_product
    assert response.status == status.HTTP_200_OK
