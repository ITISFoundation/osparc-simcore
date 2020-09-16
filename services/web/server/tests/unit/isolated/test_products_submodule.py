# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json

import pytest
from yarl import URL

from simcore_service_webserver.constants import APP_PRODUCTS_KEY, RQ_PRODUCT_KEY
from simcore_service_webserver.products import discover_product_middleware, Product
from simcore_service_webserver.statics import (
    FRONTEND_APP_DEFAULT,
    FRONTEND_APPS_AVAILABLE,
)


@pytest.fixture
def mock_app():
    class MockApp(dict):
        def __init__(self):
            super().__init__()
            self.middlewares = []

    mock_app = MockApp()
    mock_app[APP_PRODUCTS_KEY] = [
        # NOTE: try here your product host_regex before adding them in the database!
        Product(name="osparc", host_regex=r"([\.-]{0,1}osparc[\.-])"),
        Product(name="s4l", host_regex=r"(^s4l[\.-])|(^sim4life\.)|(^api.s4l[\.-])|(^api.sim4life\.)"),
        Product(name="tis", host_regex=r"(^tis[\.-])|(^ti-solutions\.)")
    ]

    return mock_app


def test_frontend_apps_available_in_sync_with_web_client(web_client_dir):

    # frontend apps in compile.json
    compile_filepath = web_client_dir / "compile.json"
    frontend_info = json.loads(compile_filepath.read_text())
    frontend_apps_in_repo = {feapp["name"] for feapp in frontend_info["applications"]}

    # compare against static consta
    assert (
        FRONTEND_APPS_AVAILABLE == frontend_apps_in_repo
    ), "Sync with values in FRONTEND_APPS_AVAILABLE with {compile_filepath}"

    assert FRONTEND_APP_DEFAULT in FRONTEND_APPS_AVAILABLE

    default_frontend_app = next(
        feapp["name"] for feapp in frontend_info["applications"] if feapp["default"]
    )
    assert (
        default_frontend_app == FRONTEND_APP_DEFAULT
    ), "Sync with values in FRONTEND_APPS_AVAILABLE with {compile_filepath}"


@pytest.mark.parametrize(
    "sample_url,expected_product",
    [
        ("https://tis-master.domain.io/", "tis"),
        ("https://s4l-staging.domain.com/v0/", "s4l"),
        ("https://osparc-master.domain.com/v0/projects", "osparc"),
        ("https://s4l.domain.com/", "s4l"),
        ("https://some-valid-but-undefined-product.io/", None),  # default?
        ("https://sim4life.io/", "s4l"),
        ("https://api.sim4life.io/", "s4l"),
        ("https://ti-solutions.io/", "tis"),
        ("https://osparc.io/", "osparc"),
        ("https://staging.osparc.io/", "osparc"),
    ],
)
async def test_middleware_product_discovery(sample_url, expected_product, mock_app):
    requested_url = URL(sample_url)

    # mocks
    class MockRequest(dict):
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
