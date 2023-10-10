# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

"""
    This tests some invariants considered in the webserver code regarding
    the structure of the frontend apps produced after compiling static-webserver/client
"""

import json
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from simcore_service_webserver.statics._constants import (
    FRONTEND_APP_DEFAULT,
    FRONTEND_APPS_AVAILABLE,
)


@pytest.fixture(scope="module")
def client_compile_cfg(web_client_dir: Path) -> dict:
    compile_filepath = web_client_dir / "compile.json"
    assert compile_filepath.exists()
    cfg = json.loads(compile_filepath.read_text())
    return cfg


@pytest.fixture(scope="module")
def source_boot_index_html(web_client_dir: Path) -> Path:
    index_html = web_client_dir / "source" / "boot" / "index.html"
    assert index_html.exists()
    return index_html


def test_expected_frontend_apps_produced_by_webclient(client_compile_cfg: dict):
    """
    tests that names in FRONTEND_APP_DEFAULT and FRONTEND_APPS_AVAILABLE
    corresponds to actual front-end apps produced by static-webserver/client
    """
    frontend_apps_in_repo = {
        feapp["name"] for feapp in client_compile_cfg["applications"]
    }

    product_names = {
        feapp["environment"]["product.name"]
        for feapp in client_compile_cfg["applications"]
    }

    # test FRONTEND_APPS_AVAILABLE
    assert (
        FRONTEND_APPS_AVAILABLE == frontend_apps_in_repo
    ), "Sync with values in FRONTEND_APPS_AVAILABLE with {compile_filepath}"

    assert (
        FRONTEND_APPS_AVAILABLE == frontend_apps_in_repo
    ), "Sync with values in FRONTEND_APPS_AVAILABLE with {compile_filepath}"

    # test FRONTEND_APP_DEFAULT
    default_frontend_app = next(
        feapp["name"]
        for feapp in client_compile_cfg["applications"]
        if feapp["default"]
    )
    assert (
        default_frontend_app == FRONTEND_APP_DEFAULT
    ), "Sync with values in FRONTEND_APPS_AVAILABLE with {compile_filepath}"

    assert FRONTEND_APP_DEFAULT in FRONTEND_APPS_AVAILABLE


async def test_static_frontend_data(client: TestClient):

    response = await client.get("/static-frontend-data.json")
    assert response.status == web.HTTPOk.status_code
    config = await response.json()
    print(config)

    assert config["appName"] == "simcore_service_webserver"
    assert config["isPaymentEnabled"] is False
